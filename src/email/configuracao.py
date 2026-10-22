from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import RAIZ, carregar

ESCOPOS_PERMITIDOS = frozenset(
    {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.labels",
    }
)

ROTULOS_SISTEMA_PROIBIDOS = frozenset({"TRASH", "SPAM", "SENT", "DRAFT", "INBOX"})
PADRAO_ROTULO_USUARIO = re.compile(r"Label_[0-9]+")


class EscopoProibido(ValueError):
    pass


class LoopbackInvalido(ValueError):
    pass


class RotuloRecusado(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConfiguracaoGmail:
    caminho_cliente: Path
    escopos: tuple[str, ...]
    url_autorizacao: str
    url_token: str
    url_api: str
    rotulo_caixa_entrada: str
    rotulos_sistema_permitidos: frozenset[str]
    listar_maximo: int
    timeout_s: float
    keychain_binario: str
    keychain_servico: str
    keychain_conta: str
    loopback_host: str
    loopback_porta: int
    espera_callback_s: float
    mensagem_callback: str
    modulo_resumo: str


def exigir_escopos_permitidos(escopos: tuple[str, ...] | list[str]) -> None:
    if not escopos:
        raise EscopoProibido("nenhum escopo configurado")
    proibidos = sorted(set(escopos) - ESCOPOS_PERMITIDOS)
    if proibidos:
        raise EscopoProibido(f"escopos fora da allowlist: {proibidos}")


def exigir_rotulos_permitidos(rotulos: list[str], sistema_permitidos: frozenset[str]) -> None:
    for rotulo in rotulos:
        if rotulo in sistema_permitidos or PADRAO_ROTULO_USUARIO.fullmatch(rotulo):
            continue
        raise RotuloRecusado(f"rotulo fora da allowlist: {rotulo!r}")


def _rotulos_sistema(bruto: list[str]) -> frozenset[str]:
    rotulos = frozenset(bruto)
    proibidos = sorted(rotulos & ROTULOS_SISTEMA_PROIBIDOS)
    if proibidos:
        raise RotuloRecusado(f"rotulos de sistema proibidos na allowlist: {proibidos}")
    return rotulos


def _teto_positivo(valor: object) -> int:
    teto = int(valor)
    if teto < 1:
        raise ValueError("listar_maximo precisa ser positivo")
    return teto


def _exigir_loopback(host: str) -> None:
    try:
        endereco = ipaddress.ip_address(host)
    except ValueError as erro:
        raise LoopbackInvalido(host) from erro
    if not endereco.is_loopback or endereco.version != 4:
        raise LoopbackInvalido(host)


def configuracao_gmail(dados: dict | None = None) -> ConfiguracaoGmail:
    bruto = (dados if dados is not None else carregar("emails"))["gmail"]
    escopos = tuple(bruto["escopos"])
    exigir_escopos_permitidos(escopos)
    keychain = bruto["keychain"]
    loopback = bruto["loopback"]
    _exigir_loopback(str(loopback["host"]))
    return ConfiguracaoGmail(
        caminho_cliente=RAIZ / bruto["cliente"],
        escopos=escopos,
        url_autorizacao=bruto["url_autorizacao"],
        url_token=bruto["url_token"],
        url_api=bruto["url_api"].rstrip("/"),
        rotulo_caixa_entrada=bruto["rotulo_caixa_entrada"],
        rotulos_sistema_permitidos=_rotulos_sistema(bruto["rotulos_sistema_permitidos"]),
        listar_maximo=_teto_positivo(bruto["listar_maximo"]),
        timeout_s=float(bruto["timeout_s"]),
        keychain_binario=keychain["binario"],
        keychain_servico=keychain["servico"],
        keychain_conta=keychain["conta"],
        loopback_host=str(loopback["host"]),
        loopback_porta=int(loopback["porta"]),
        espera_callback_s=float(loopback["espera_s"]),
        mensagem_callback=loopback["mensagem"],
        modulo_resumo=bruto["modulo_resumo"],
    )
