from __future__ import annotations

from datetime import date

from src.coletor.alertas_cartao import extrair_cartoes, vaga_do_cartao
from src.coletor.alertas_config import PlataformaAlertas, configuracao_alertas
from src.coletor.contratos import ResultadoColeta, VagaBruta
from src.email.regras import regras
from src.email.remetente import remetente_confiavel as remetente_confiavel_src

CONSTANTES_DO_CONFIG = {
    "LINK_VAGA": "link_vaga",
    "ROTULOS_LINK": "rotulos_link",
    "RUIDO": "ruido",
}


def _plataforma() -> PlataformaAlertas:
    return configuracao_alertas().plataformas[regras().plataforma_alertas]


def __getattr__(nome: str):
    if nome in CONSTANTES_DO_CONFIG:
        return getattr(_plataforma(), CONSTANTES_DO_CONFIG[nome])
    raise AttributeError(nome)


def remetente_confiavel(remetente: str) -> bool:
    return remetente_confiavel_src(remetente, regras().plataforma_alertas)


def extrair_alerta_linkedin(
    remetente: str,
    corpo: str,
    recebido_em: date | None = None,
) -> list[VagaBruta]:
    if not remetente_confiavel(remetente):
        return []
    plataforma = _plataforma()
    achados = extrair_cartoes(corpo, plataforma, configuracao_alertas().corpo_max_chars)
    return [vaga_do_cartao(cartao, plataforma, recebido_em) for cartao in achados.completos]


def coletar_de_emails(emails: list[tuple[str, str]]) -> ResultadoColeta:
    resultado = ResultadoColeta(fonte=_plataforma().fonte)
    resultado.robots_permite = None
    resultado.evidencia["caminho"] = "email de alerta no Gmail, o site nunca e automatizado"
    resultado.evidencia["emails_lidos"] = len(emails)
    descartados = 0
    for remetente, corpo in emails:
        if not remetente_confiavel(remetente):
            descartados += 1
            continue
        resultado.vagas.extend(extrair_alerta_linkedin(remetente, corpo))
    resultado.evidencia["emails_descartados_por_remetente"] = descartados
    return resultado
