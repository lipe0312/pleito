from __future__ import annotations

from typing import Protocol

from src.config import carregar
from src.email.modelo import Etapa


class RotuloAusente(LookupError):
    pass


class FonteDeRotulos(Protocol):
    def rotulos(self) -> list[dict]: ...


def rotulo_da_etapa(etapa: Etapa) -> str:
    return carregar("rotulos")["etapas"][etapa.value]


def resolver_rotulos(fonte: FonteDeRotulos) -> dict[Etapa, str]:
    da_conta = {rotulo["name"]: rotulo["id"] for rotulo in fonte.rotulos()}
    resolvidos = {}
    for etapa in Etapa:
        nome = rotulo_da_etapa(etapa)
        if nome not in da_conta:
            raise RotuloAusente(f"rotulo {nome!r} nao existe na conta")
        resolvidos[etapa] = da_conta[nome]
    return resolvidos
