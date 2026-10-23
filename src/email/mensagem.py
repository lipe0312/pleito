from __future__ import annotations

import base64
import binascii

from src.email.modelo import Email

TIPO_TEXTO = "text/plain"


def _primeiro_cabecalho(cabecalhos: list[dict], nome: str) -> str:
    procurado = nome.lower()
    for cabecalho in cabecalhos:
        if str(cabecalho.get("name", "")).lower() == procurado:
            return str(cabecalho.get("value", ""))
    return ""


def _decodificar(dados: str) -> str:
    try:
        bruto = base64.urlsafe_b64decode(dados + "=" * (-len(dados) % 4))
    except (binascii.Error, ValueError):
        return ""
    return bruto.decode("utf-8", errors="replace")


def _texto_simples(parte: dict) -> str:
    if parte.get("mimeType") == TIPO_TEXTO and parte.get("body", {}).get("data"):
        return _decodificar(parte["body"]["data"])
    for filha in parte.get("parts", []) or []:
        texto = _texto_simples(filha)
        if texto:
            return texto
    return ""


def email_de_mensagem(mensagem: dict) -> Email:
    carga = mensagem.get("payload", {}) or {}
    cabecalhos = carga.get("headers", []) or []
    return Email(
        remetente=_primeiro_cabecalho(cabecalhos, "From"),
        assunto=_primeiro_cabecalho(cabecalhos, "Subject"),
        corpo=_texto_simples(carga) or str(mensagem.get("snippet", "")),
        reply_to=_primeiro_cabecalho(cabecalhos, "Reply-To"),
        autenticacao=_primeiro_cabecalho(cabecalhos, "Authentication-Results"),
    )
