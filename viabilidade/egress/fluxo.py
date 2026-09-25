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
MARCAS_CONFIRMACAO = (
    "candidatura enviada",
    "candidatura efetuada",
    "recebemos sua candidatura",
    "application received",
    "thanks for applying",
    "obrigado por se candidatar",
)
MARCAS_CAPTCHA = ("recaptcha", "hcaptcha", "cf-turnstile", "captcha")


class EtapaEgress(StrEnum):
    ABRIR = "abrir_pagina"
    DETECTAR_LOGIN = "detectar_login"
    DETECTAR_CAPTCHA = "detectar_captcha"
    ACHAR_FORMULARIO = "achar_formulario"
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
            "motivos": [m.value for m in self.motivos],
            "erro": self.erro,
            "veredito": self.veredito().value,
            "executado_em": self.executado_em.isoformat(),
        }
        destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return destino


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
            resposta = pagina.goto(url, wait_until="domcontentloaded")
            resultado.marcar(EtapaEgress.ABRIR, bool(resposta and resposta.ok))
            _capturar(pagina, resultado, "01_aberta")

            conteudo = pagina.content().lower()

            tem_captcha = any(m in conteudo for m in MARCAS_CAPTCHA)
            resultado.marcar(EtapaEgress.DETECTAR_CAPTCHA, tem_captcha)
            if tem_captcha:
                resultado.motivos.append(MotivoNoGo.CAPTCHA)

            formulario = pagina.locator("form").first
            tem_form = formulario.count() > 0
            resultado.marcar(EtapaEgress.ACHAR_FORMULARIO, tem_form)

            anexo = pagina.locator(SELETORES_ANEXO[0]).first
            tem_anexo = anexo.count() > 0
            resultado.marcar(EtapaEgress.ACHAR_ANEXO, tem_anexo)

            if tem_anexo:
                anexo.set_input_files(str(pdf))
                resultado.marcar(EtapaEgress.ANEXAR_PDF, True)
                _capturar(pagina, resultado, "02_anexado")

            for campo in pagina.locator("input, textarea, select").all()[:60]:
                resultado.campos_detectados.append(
                    {
                        "tag": campo.evaluate("e => e.tagName.toLowerCase()"),
                        "tipo": campo.get_attribute("type") or "",
                        "nome": campo.get_attribute("name") or "",
                        "rotulo": (campo.get_attribute("aria-label") or "")[:120],
                        "obrigatorio": campo.get_attribute("required") is not None,
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
                _capturar(pagina, resultado, "03_parado_antes_do_submit")
                resultado.marcar(EtapaEgress.SUBMETER, False)
                return resultado

            exigir_submit_autorizado()
            if submit is None:
                resultado.motivos.append(MotivoNoGo.SEM_PROVA_ENVIO)
                return resultado

            submit.click()
            pagina.wait_for_load_state("networkidle", timeout=30000)
            resultado.marcar(EtapaEgress.SUBMETER, True)
            _capturar(pagina, resultado, "04_pos_submit")

            final = pagina.content().lower()
            confirmado = any(m in final for m in MARCAS_CONFIRMACAO)
            resultado.marcar(EtapaEgress.DETECTAR_CONFIRMACAO, confirmado)
            if not confirmado:
                resultado.motivos.append(MotivoNoGo.SEM_PROVA_ENVIO)
    except Exception as exc:
        resultado.erro = f"{type(exc).__name__}: {exc}"

    return resultado
