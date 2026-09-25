from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from viabilidade.config import ambiente
from viabilidade.contratos import MotivoNoGo, Veredito
from viabilidade.egress.navegador import exigir_submit_autorizado, navegador_persistente

SELETORES_SUBMIT = (
    "button[type=submit]",
    "input[type=submit]",
    "button:has-text('Candidatar')",
    "button:has-text('Enviar candidatura')",
    "button:has-text('Submit application')",
    "button:has-text('Apply')",
)
SELETORES_ANEXO = ("input[type=file]",)
SELETORES_APLICAR = (
    "[data-testid*=apply]",
    "a[href*=apply]",
    "a[href*=candidat]",
    "button:has-text('Candidatar')",
    "button:has-text('Apply')",
)
MARCAS_LOGIN = ("faca login", "faça login", "sign in to apply", "entre para se candidatar")
URLS_LOGIN = ("/signin", "/sign-in", "/login", "/entrar", "/auth", "/candidates/signin")
CAMPOS_SENHA = ("input[type=password]",)
MINIMO_CAMPOS_FORMULARIO = 3
ESPERA_RENDER_MS = 2500
MARCAS_CONFIRMACAO = (
    "candidatura enviada",
    "candidatura efetuada",
    "recebemos sua candidatura",
    "application received",
    "thanks for applying",
    "obrigado por se candidatar",
)
SELETORES_CAPTCHA = (
    "iframe[src*=recaptcha]",
    "iframe[src*=hcaptcha]",
    "iframe[title*=captcha]",
    ".g-recaptcha",
    ".h-captcha",
    ".cf-turnstile",
    "[data-sitekey]",
)
MARCAS_SCRIPT_CAPTCHA = ("recaptcha", "hcaptcha", "cf-turnstile")


class EtapaEgress(StrEnum):
    ABRIR = "abrir_pagina"
    DETECTAR_LOGIN = "detectar_login"
    DETECTAR_CAPTCHA = "detectar_captcha"
    ACHAR_FORMULARIO = "achar_formulario"
    SEGUIR_APLICAR = "seguir_link_aplicar"
    SEM_MURO_DE_LOGIN = "sem_muro_de_login"
    SEM_CAPTCHA_VISIVEL = "sem_captcha_visivel"
    ACHAR_ANEXO = "achar_anexo"
    ANEXAR_PDF = "anexar_pdf"
    MAPEAR_CAMPOS = "mapear_campos"
    ACHAR_SUBMIT = "achar_submit"
    SUBMETER = "submeter"
    DETECTAR_CONFIRMACAO = "detectar_confirmacao"


@dataclass(slots=True)
class ResultadoEgress:
    url: str
    modo: str
    etapas: dict[str, bool] = field(default_factory=dict)
    campos_detectados: list[dict] = field(default_factory=list)
    capturas: list[str] = field(default_factory=list)
    evidencia: dict = field(default_factory=dict)
    motivos: list[MotivoNoGo] = field(default_factory=list)
    erro: str | None = None
    executado_em: datetime = field(default_factory=lambda: datetime.now(UTC))

    def marcar(self, etapa: EtapaEgress, ok: bool) -> bool:
        self.etapas[etapa.value] = ok
        return ok

    def veredito(self) -> Veredito:
        if self.erro or self.motivos:
            return Veredito.NO_GO
        obrigatorias = (
            EtapaEgress.SEM_CAPTCHA_VISIVEL,
            EtapaEgress.SEM_MURO_DE_LOGIN,
            EtapaEgress.ABRIR,
            EtapaEgress.ACHAR_FORMULARIO,
            EtapaEgress.ACHAR_ANEXO,
            EtapaEgress.ANEXAR_PDF,
            EtapaEgress.ACHAR_SUBMIT,
        )
        if not all(self.etapas.get(e.value) for e in obrigatorias):
            return Veredito.NO_GO
        if self.modo == "dry_run":
            return Veredito.GO_COM_RESSALVA
        return (
            Veredito.GO
            if self.etapas.get(EtapaEgress.DETECTAR_CONFIRMACAO.value)
            else Veredito.NO_GO
        )

    def salvar(self, destino: Path) -> Path:
        destino.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "url": self.url,
            "modo": self.modo,
            "etapas": self.etapas,
            "campos_detectados": self.campos_detectados,
            "capturas": self.capturas,
            "evidencia": self.evidencia,
            "motivos": [m.value for m in self.motivos],
            "erro": self.erro,
            "veredito": self.veredito().value,
            "executado_em": self.executado_em.isoformat(),
        }
        destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return destino


def _assentar(pagina) -> str:
    estado = "networkidle"
    try:
        pagina.wait_for_load_state("networkidle", timeout=25000)
    except Exception as exc:
        estado = f"sem networkidle: {type(exc).__name__}"
    pagina.wait_for_timeout(ESPERA_RENDER_MS)
    return estado


def _tem_formulario(pagina) -> tuple[bool, int, int]:
    formularios = pagina.locator("form").count()
    campos = pagina.locator("input, textarea, select").count()
    return (formularios > 0 or campos >= MINIMO_CAMPOS_FORMULARIO), formularios, campos


def _capturar(pagina, resultado: ResultadoEgress, nome: str) -> None:
    env = ambiente()
    pasta = env.dados / "viabilidade" / "egress"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{resultado.executado_em:%Y%m%dT%H%M%S}_{nome}.png"
    pagina.screenshot(path=str(caminho), full_page=True)
    resultado.capturas.append(str(caminho))


def executar_fluxo(url: str, pdf: Path, respostas: dict[str, str]) -> ResultadoEgress:
    env = ambiente()
    resultado = ResultadoEgress(url=url, modo=env.egress_modo)

    if not pdf.exists():
        resultado.erro = f"pdf inexistente: {pdf}"
        return resultado

    try:
        with navegador_persistente() as contexto:
            pagina = contexto.new_page()
            resposta = pagina.goto(url, wait_until="domcontentloaded", timeout=45000)
            _assentar(pagina)
            resultado.marcar(EtapaEgress.ABRIR, bool(resposta and resposta.ok))
            _capturar(pagina, resultado, "01_aberta")

            conteudo = pagina.content().lower()

            widgets = 0
            visiveis = 0
            for seletor in SELETORES_CAPTCHA:
                alvo = pagina.locator(seletor)
                achados = alvo.count()
                widgets += achados
                if achados and alvo.first.is_visible():
                    visiveis += 1
            script = [m for m in MARCAS_SCRIPT_CAPTCHA if m in conteudo]

            resultado.evidencia["captcha_widgets"] = widgets
            resultado.evidencia["captcha_widgets_visiveis"] = visiveis
            resultado.evidencia["captcha_scripts"] = script
            resultado.marcar(EtapaEgress.SEM_CAPTCHA_VISIVEL, visiveis == 0)
            resultado.marcar(EtapaEgress.DETECTAR_CAPTCHA, visiveis > 0)
            if visiveis:
                resultado.motivos.append(MotivoNoGo.CAPTCHA)

            tem_form, n_form, n_campos = _tem_formulario(pagina)
            resultado.evidencia["formularios"] = n_form
            resultado.evidencia["campos_na_pagina"] = n_campos
            resultado.marcar(EtapaEgress.SEM_MURO_DE_LOGIN, True)

            if not tem_form:
                seguido = False
                for seletor in SELETORES_APLICAR:
                    alvo = pagina.locator(seletor).first
                    if alvo.count() == 0:
                        continue
                    try:
                        alvo.click(timeout=15000)
                        _assentar(pagina)
                        seguido = True
                    except Exception as exc:
                        resultado.evidencia["falha_ao_seguir_aplicar"] = str(exc)[:160]
                    break
                resultado.marcar(EtapaEgress.SEGUIR_APLICAR, seguido)
                if seguido:
                    resultado.evidencia["url_apos_aplicar"] = pagina.url[:200]
                    _capturar(pagina, resultado, "02_pos_aplicar")
                    tem_form, n_form, n_campos = _tem_formulario(pagina)
                    resultado.evidencia["formularios_pos_aplicar"] = n_form
                    resultado.evidencia["campos_pos_aplicar"] = n_campos
                    conteudo = pagina.content().lower()

            url_atual = pagina.url.lower()
            muro = (
                any(marca in url_atual for marca in URLS_LOGIN)
                or pagina.locator(CAMPOS_SENHA[0]).count() > 0
                or any(m in conteudo for m in MARCAS_LOGIN)
            )
            resultado.marcar(EtapaEgress.SEM_MURO_DE_LOGIN, not muro)
            if muro:
                resultado.motivos.append(MotivoNoGo.EXIGE_LOGIN)
                resultado.evidencia["muro_de_login"] = (
                    "o formulario de candidatura exige sessao autenticada; resolvel com login "
                    "manual uma vez no perfil persistente, o sistema nunca digita senha"
                )
                tem_form = False

            resultado.marcar(EtapaEgress.ACHAR_FORMULARIO, tem_form)

            anexo = pagina.locator(SELETORES_ANEXO[0]).first
            tem_anexo = anexo.count() > 0
            resultado.marcar(EtapaEgress.ACHAR_ANEXO, tem_anexo)

            if tem_anexo:
                anexo.set_input_files(str(pdf))
                resultado.marcar(EtapaEgress.ANEXAR_PDF, True)
                _capturar(pagina, resultado, "03_anexado")

            for campo in pagina.locator("input, textarea, select").all()[:80]:
                nome = campo.get_attribute("name") or ""
                identificador = campo.get_attribute("id") or ""
                rotulo = campo.get_attribute("aria-label") or ""
                if not rotulo and identificador:
                    etiqueta = pagina.locator(f'label[for="{identificador}"]')
                    if etiqueta.count():
                        rotulo = (etiqueta.first.inner_text() or "").strip()
                resultado.campos_detectados.append(
                    {
                        "tag": campo.evaluate("e => e.tagName.toLowerCase()"),
                        "tipo": campo.get_attribute("type") or "",
                        "nome": nome,
                        "id": identificador,
                        "rotulo": rotulo[:120],
                        "obrigatorio": campo.get_attribute("required") is not None
                        or campo.get_attribute("aria-required") == "true",
                    }
                )
            resultado.marcar(EtapaEgress.MAPEAR_CAMPOS, bool(resultado.campos_detectados))

            submit = None
            for seletor in SELETORES_SUBMIT:
                candidato = pagina.locator(seletor).first
                if candidato.count() > 0:
                    submit = candidato
                    break
            resultado.marcar(EtapaEgress.ACHAR_SUBMIT, submit is not None)

            if env.egress_modo == "dry_run":
                _capturar(pagina, resultado, "04_parado_antes_do_submit")
                resultado.marcar(EtapaEgress.SUBMETER, False)
                return resultado

            exigir_submit_autorizado()
            if submit is None:
                resultado.motivos.append(MotivoNoGo.SEM_PROVA_ENVIO)
                return resultado

            submit.click()
            _assentar(pagina)
            resultado.marcar(EtapaEgress.SUBMETER, True)
            _capturar(pagina, resultado, "05_pos_submit")

            final = pagina.content().lower()
            confirmado = any(m in final for m in MARCAS_CONFIRMACAO)
            resultado.marcar(EtapaEgress.DETECTAR_CONFIRMACAO, confirmado)
            if not confirmado:
                resultado.motivos.append(MotivoNoGo.SEM_PROVA_ENVIO)
    except Exception as exc:
        resultado.erro = f"{type(exc).__name__}: {exc}"

    return resultado
