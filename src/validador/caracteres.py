from __future__ import annotations

import unicodedata

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.resultado import Regra, Violacao


def _codigo(caractere: str) -> str:
    return f"U+{ord(caractere):04X}"


def validar_travessao(texto: str, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.caracteres
    achados = sorted({c for c in texto if c in regras.proibidos})
    detalhes = [_codigo(c) for c in achados]
    detalhes += [repr(seq) for seq in regras.sequencias_proibidas if seq in texto]
    return [Violacao(Regra.TRAVESSAO, f"travessao proibido: {d}") for d in detalhes]


def validar_invisiveis(texto: str, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.caracteres
    achados = sorted(
        {
            c
            for c in texto
            if c not in regras.controles_permitidos
            and unicodedata.category(c) in regras.categorias_unicode_proibidas
        }
    )
    return [
        Violacao(Regra.CARACTERE_INVISIVEL, f"caractere invisivel ou de controle {_codigo(c)}")
        for c in achados
    ]


def _letra_permitida(caractere: str, config: ConfiguracaoValidador) -> bool:
    regras = config.caracteres.alfabeto
    if caractere in regras.extras:
        return True
    script = unicodedata.name(caractere, "").split(" ")[0]
    base = unicodedata.normalize("NFD", caractere)[0]
    if script not in regras.scripts:
        return False
    return base.isascii() or script not in regras.scripts_com_base_ascii


def validar_alfabeto(texto: str, config: ConfiguracaoValidador) -> list[Violacao]:
    achados = sorted(
        {
            c
            for c in texto
            if unicodedata.category(c).startswith("L") and not _letra_permitida(c, config)
        }
    )
    return [
        Violacao(Regra.ALFABETO, f"letra fora do alfabeto permitido {_codigo(c)}") for c in achados
    ]
