from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from html.parser import HTMLParser

from src.conteudo.sincronizacao import ConfiguracaoSincronizacao, Tecnologia

SEPARADOR_DE_FRASE = re.compile(r"(?<=[.!?])\s+|[\r\n]+")
ESPACOS = re.compile(r"\s+")
TAGS_IGNORADAS = frozenset({"script", "style", "noscript", "template", "svg"})


def limpar_texto(texto: str, max_chars: int) -> str:
    visivel = "".join(" " if unicodedata.category(c).startswith("C") else c for c in texto)
    return ESPACOS.sub(" ", visivel).strip()[:max_chars]


class _ExtratorHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.descricao = ""
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in TAGS_IGNORADAS:
            self._ignorando += 1
        if tag == "meta" and dict(attrs).get("name", "").lower() == "description":
            self.descricao = dict(attrs).get("content") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag in TAGS_IGNORADAS and self._ignorando:
            self._ignorando -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            self.partes.append(data)


def texto_da_pagina(html: str, max_chars: int) -> tuple[str, str]:
    extrator = _ExtratorHtml()
    extrator.feed(html)
    extrator.close()
    return "\n".join(extrator.partes)[:max_chars], extrator.descricao


def frases_sem_instrucao(texto: str, padroes: Iterable[re.Pattern[str]]) -> list[str]:
    frases = [frase.strip() for frase in SEPARADOR_DE_FRASE.split(texto) if frase.strip()]
    return [f for f in frases if not any(p.search(f) for p in padroes)]


def _contem_termo(frases: list[str], termo: str) -> bool:
    padrao = re.compile(rf"(?<!\w){re.escape(termo)}(?!\w)", re.IGNORECASE)
    return any(padrao.search(frase) for frase in frases)


def _estruturais(entrada: Tecnologia, linguagens: set[str], topics: set[str]) -> list[str]:
    achados = [f"linguagem:{n}" for n in entrada.linguagens if n.lower() in linguagens]
    return achados + [f"topic:{t}" for t in entrada.topics if t.lower() in topics]


def extrair_tecnologias(
    config: ConfiguracaoSincronizacao,
    linguagens: Iterable[str],
    topics: Iterable[str],
    texto: str,
    origem: str,
) -> dict[str, list[str]]:
    nomes_linguagens = {n.lower() for n in linguagens}
    nomes_topics = {t.lower() for t in topics}
    achadas = {e.tech: _estruturais(e, nomes_linguagens, nomes_topics) for e in config.dicionario}
    sustentadas = {tech for tech, achados in achadas.items() if achados}
    frases = frases_sem_instrucao(texto, config.padroes_instrucao)
    for entrada in config.dicionario:
        if origem == "github" and not (set(entrada.requer) & sustentadas):
            continue
        marca = "readme" if origem == "github" else "pagina"
        achadas[entrada.tech] += [
            f"{marca}:{termo}" for termo in entrada.termos if _contem_termo(frases, termo)
        ]
    return {tech: achados for tech, achados in achadas.items() if achados}
