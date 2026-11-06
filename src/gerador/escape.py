from __future__ import annotations

import re
import unicodedata

from src.gerador.erros import SlotInvalido, TechForaDoInventario

TABELA = str.maketrans(
    {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
        '"': r"\textquotedbl{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
        "|": r"\textbar{}",
        "`": r"\textasciigrave{}",
        "[": "{[}",
        "]": "{]}",
    }
)
CATEGORIAS_PROIBIDAS = ("C", "Zl", "Zp")


class LatexSeguro(str):
    __slots__ = ()


def escapar_latex(texto: str) -> str:
    return texto.translate(TABELA)


def texto_limpo(valor: object, max_chars: int, nome: str) -> str:
    if not isinstance(valor, str):
        raise SlotInvalido(f"{nome}: precisa ser texto")
    texto = unicodedata.normalize("NFC", valor).strip()
    if not texto:
        raise SlotInvalido(f"{nome}: vazio")
    if len(texto) > max_chars:
        raise SlotInvalido(f"{nome}: {len(texto)} caracteres, limite {max_chars}")
    proibido = next(
        (c for c in texto if unicodedata.category(c).startswith(CATEGORIAS_PROIBIDAS)), None
    )
    if proibido is not None:
        raise SlotInvalido(f"{nome}: caractere de controle U+{ord(proibido):04X}")
    return texto


def url_segura(valor: object, padrao: str, nome: str) -> str:
    if not isinstance(valor, str) or not re.fullmatch(padrao, valor):
        raise SlotInvalido(f"{nome}: endereco fora do padrao permitido")
    return valor


def compor_texto(
    texto: str, techs: list[str], permitidas: set[str] | frozenset[str]
) -> LatexSeguro:
    fora = sorted(set(techs) - set(permitidas))
    if fora:
        raise TechForaDoInventario(f"tecnologia fora do inventario: {fora}")
    if not techs:
        return LatexSeguro(escapar_latex(texto))
    nomes = "|".join(re.escape(tech) for tech in sorted(set(techs), key=len, reverse=True))
    pedacos = re.split(rf"(?<!\w)({nomes})(?!\w)", texto)
    saida = [
        rf"\tech{{{escapar_latex(pedaco)}}}" if indice % 2 else escapar_latex(pedaco)
        for indice, pedaco in enumerate(pedacos)
    ]
    return LatexSeguro("".join(saida))
