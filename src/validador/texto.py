from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple

from src.conteudo.decompor import ESCAPE
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.resultado import Regra, Violacao

DESTINO_DO_LINK = re.compile(r"\\href\s*\{([^{}]*)\}")
SIMBOLO_DE_CONTROLE = re.compile(r"\\[^A-Za-z]", re.S)
COMANDO_COM_LETRAS = re.compile(r"\\[A-Za-z]+")
PALAVRA = re.compile(r"\w+")


class Palavra(NamedTuple):
    forma: str
    inicio: int
    fim: int


def normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def palavras(texto: str) -> list[Palavra]:
    return [Palavra(normalizar(m.group()), m.start(), m.end()) for m in PALAVRA.finditer(texto)]


def plano(trecho: str, config: ConfiguracaoValidador) -> str:
    limpo = DESTINO_DO_LINK.sub(" ", trecho)
    for nome, total in config.latex.medidas.comandos.items():
        argumentos = r"(?:\s*\{[^{}]*\})" * total
        limpo = re.sub(rf"\\{re.escape(nome)}(?![A-Za-z])\*?{argumentos}", " ", limpo)
    limpo = ESCAPE.sub(r"\1", limpo)
    limpo = SIMBOLO_DE_CONTROLE.sub(" ", limpo)
    limpo = COMANDO_COM_LETRAS.sub(" ", limpo)
    return " ".join(limpo.replace("{", "").replace("}", "").split())


def recorte(texto: str, config: ConfiguracaoValidador) -> str:
    return texto[: config.conteudo.trecho_max_chars]


def ao_redor(texto: str, inicio: int, fim: int, config: ConfiguracaoValidador) -> str:
    margem = config.conteudo.trecho_max_chars // 4
    return recorte(texto[max(0, inicio - margem) : fim + margem].strip(), config)


def violacao(
    config: ConfiguracaoValidador, regra: Regra, detalhe: str, trecho: str, sugestao: str
) -> Violacao:
    return Violacao(regra, detalhe, recorte(trecho, config), sugestao)


def ocorrencias(texto: list[Palavra], sequencia: list[str]) -> list[int]:
    if not sequencia:
        return []
    tamanho = len(sequencia)
    formas = [p.forma for p in texto]
    return [i for i in range(len(formas) - tamanho + 1) if formas[i : i + tamanho] == sequencia]
