from __future__ import annotations

import re
from functools import lru_cache
from html import escape
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
MODELOS = Path(__file__).resolve().parent / "templates"


class HtmlSeguro(str):
    __slots__ = ()


def _valor(valor: object) -> str:
    if isinstance(valor, HtmlSeguro):
        return str(valor)
    return escape(str(valor), quote=True)


def renderizar(modelo: str, **valores: object) -> HtmlSeguro:
    return HtmlSeguro(PLACEHOLDER.sub(lambda achado: _valor(valores[achado.group(1)]), modelo))


@lru_cache(maxsize=32)
def modelo(nome: str) -> str:
    return (MODELOS / nome).read_text(encoding="utf-8")


def juntar(fragmentos: list[HtmlSeguro]) -> HtmlSeguro:
    return HtmlSeguro("".join(fragmentos))
