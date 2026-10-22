from __future__ import annotations

import re

from src.email.modelo import Email, Motivo
from src.email.regras import Regras, normalizar, regras

ENDERECO = re.compile(r"<([^>]+)>\s*$")


def endereco_de(remetente: str) -> str:
    bruto = (remetente or "").strip().lower()
    achado = ENDERECO.search(bruto)
    return (achado.group(1) if achado else bruto).strip()


def nome_exibicao_de(remetente: str) -> str:
    bruto = (remetente or "").strip()
    achado = ENDERECO.search(bruto)
    return bruto[: achado.start()].strip() if achado else ""


def _partes(endereco: str) -> tuple[str, str]:
    if endereco.count("@") != 1 or any(c.isspace() for c in endereco):
        return "", ""
    caixa, _, dominio = endereco.partition("@")
    if not caixa or not dominio:
        return "", ""
    return caixa, dominio


def dominio_de(remetente: str) -> str:
    return _partes(endereco_de(remetente))[1]


def plataforma_de(remetente: str, configuradas: Regras | None = None) -> str | None:
    configuradas = configuradas or regras()
    caixa, dominio = _partes(endereco_de(remetente))
    if not dominio:
        return None
    for plataforma in configuradas.plataformas.values():
        if dominio in plataforma.dominios and (
            not plataforma.caixas or caixa in plataforma.caixas
        ):
            return plataforma.nome
    return None


def remetente_confiavel(
    remetente: str, plataforma: str | None = None, configuradas: Regras | None = None
) -> bool:
    achada = plataforma_de(remetente, configuradas)
    return achada is not None and (plataforma is None or achada == plataforma)


def _dominio_de_plataforma(dominio: str, configuradas: Regras) -> bool:
    return any(dominio in p.dominios for p in configuradas.plataformas.values())


def _imita_plataforma(dominio: str, configuradas: Regras) -> bool:
    if not dominio or _dominio_de_plataforma(dominio, configuradas):
        return False
    return any(
        marca in dominio for p in configuradas.plataformas.values() for marca in p.marcas
    )


def _fora_do_ascii(dominio: str) -> bool:
    return not dominio.isascii() or "xn--" in dominio


def _nome_de_plataforma_alheia(nome: str, dominio: str, configuradas: Regras) -> bool:
    normalizado = normalizar(nome)
    return any(
        marca in normalizado and dominio not in plataforma.dominios
        for plataforma in configuradas.plataformas.values()
        for marca in plataforma.marcas
    )


def motivo_forjado(email: Email, configuradas: Regras | None = None) -> Motivo | None:
    configuradas = configuradas or regras()
    dominio = dominio_de(email.remetente)
    dominio_reply = dominio_de(email.reply_to) if email.reply_to else ""
    if _fora_do_ascii(endereco_de(email.remetente)) or (
        email.reply_to and _fora_do_ascii(endereco_de(email.reply_to))
    ):
        return Motivo.DOMINIO_FORA_DO_ASCII
    if _imita_plataforma(dominio, configuradas):
        return Motivo.DOMINIO_IMITA_PLATAFORMA
    if _nome_de_plataforma_alheia(nome_exibicao_de(email.remetente), dominio, configuradas):
        return Motivo.NOME_DE_EXIBICAO_DE_PLATAFORMA
    if email.reply_to:
        if _imita_plataforma(dominio_reply, configuradas):
            return Motivo.REPLY_TO_IMITA_PLATAFORMA
        nome = plataforma_de(email.remetente, configuradas)
        if nome and dominio_reply not in configuradas.plataformas[nome].dominios:
            return Motivo.REPLY_TO_DIVERGENTE
    compacta = normalizar(email.autenticacao).replace(" ", "")
    if any(falha in compacta for falha in configuradas.autenticacao_falhas):
        return Motivo.AUTENTICACAO_FALHOU
    return None
