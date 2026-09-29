from __future__ import annotations

import re

from src.coletor.contratos import Funcao
from src.config import carregar

_CONFIG = carregar("triagem")
_LIMITES = _CONFIG["limites"]
LIMITE_DESCRICAO_UTIL = int(_LIMITES["descricao_util_min_chars"])
LIMITE_TEXTO_FUNCAO = int(_LIMITES["descricao_funcao_max_chars"])
LIMITE_TEXTO_ANOS = int(_LIMITES["descricao_anos_max_chars"])
LIMITE_ANOS_MINIMO = int(_LIMITES["anos_experiencia_min_detectavel"])
LIMITE_ANOS_EXPERIENCIA = int(_LIMITES["anos_experiencia_max_detectavel"])
TERMOS_FUNCAO = {
    Funcao(funcao): tuple(termos) for funcao, termos in _CONFIG["termos_funcao"].items()
}
TERMOS_FORA = tuple(_CONFIG["termos_fora"])
SIGLAS_FUNCAO = {
    Funcao(funcao): tuple(siglas) for funcao, siglas in _CONFIG["siglas_funcao"].items()
}
TERMOS_GENERICOS = frozenset(_CONFIG["termos_genericos"])

ANOS = re.compile(
    r"\b(\d{1,2})\s*(?:\+|\-\s*\d{1,2})?\s*(?:years?|yrs?|anos?)\b(?![^.]{0,20}old)",
    re.IGNORECASE,
)


def _tem_sigla(texto: str, siglas: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{s}\b", texto) for s in siglas)


def inferir_funcao(titulo: str, descricao: str = "") -> Funcao:
    baixo = f" {titulo.lower()} "
    for funcao, termos in TERMOS_FUNCAO.items():
        if any(termo in baixo for termo in termos):
            return funcao
    for funcao, siglas in SIGLAS_FUNCAO.items():
        if _tem_sigla(baixo, siglas):
            return funcao
    if any(termo in baixo for termo in TERMOS_FORA):
        return Funcao.OUTRA
    if "engineer" in baixo or "engenheir" in baixo:
        return Funcao.ENGENHARIA
    if "estagi" in baixo and "desenvolv" in baixo:
        return Funcao.ENGENHARIA
    corpo = (descricao or "")[:LIMITE_TEXTO_FUNCAO].lower()
    for funcao, termos in TERMOS_FUNCAO.items():
        especificos = [termo for termo in termos if termo not in TERMOS_GENERICOS]
        if any(termo in corpo for termo in especificos):
            return funcao
    return Funcao.INDEFINIDA


def extrair_anos_experiencia(descricao: str) -> int | None:
    if not descricao:
        return None
    achados = [int(match.group(1)) for match in ANOS.finditer(descricao[:LIMITE_TEXTO_ANOS])]
    plausiveis = [
        anos for anos in achados if LIMITE_ANOS_MINIMO <= anos <= LIMITE_ANOS_EXPERIENCIA
    ]
    return min(plausiveis) if plausiveis else None
