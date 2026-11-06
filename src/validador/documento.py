from __future__ import annotations

import re
from dataclasses import dataclass

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.latex import sem_comentarios
from src.validador.texto import normalizar, plano

SECAO = re.compile(r"\\section\*?\{((?:[^{}\\]|\\.)*)\}")
CENTRO = re.compile(r"\\begin\s*\{center\}(.*?)\\end\s*\{center\}", re.S)
ENTRADA = re.compile(r"^[ \t]*\\textbf\{(?P<titulo>(?:[^{}\\]|\\.)*)\}(?P<resto>[^\n]*)$", re.M)
LISTA = re.compile(r"\\begin\{itemize\}(?P<itens>.*?)\\end\{itemize\}", re.S)
ITEM = re.compile(r"\\item(?![A-Za-z])")
HFILL = re.compile(r"\\hfill(?![A-Za-z])")


@dataclass(frozen=True, slots=True)
class Entrada:
    titulo: str
    complemento: str
    fim: str
    bullets: tuple[str, ...]
    solto: str


def _itens(trecho: str) -> tuple[str, ...]:
    itens = []
    for lista in LISTA.finditer(trecho):
        itens += [" ".join(i.split()) for i in ITEM.split(lista["itens"]) if i.strip()]
    return tuple(itens)


@dataclass(frozen=True, slots=True)
class Secao:
    titulo: str
    conteudo: str

    def antes_da_primeira_entrada(self) -> str:
        primeira = ENTRADA.search(self.conteudo)
        return self.conteudo[: primeira.start()] if primeira else self.conteudo

    def entradas(self) -> tuple[Entrada, ...]:
        achados = list(ENTRADA.finditer(self.conteudo))
        entradas = []
        for posicao, achado in enumerate(achados):
            limite = achados[posicao + 1].start() if posicao + 1 < len(achados) else None
            regiao = self.conteudo[achado.end() : limite]
            resto = achado["resto"]
            marca = HFILL.search(resto)
            complemento = resto[: marca.start()] if marca else resto
            fim = resto[marca.end() :] if marca else ""
            entradas.append(
                Entrada(
                    titulo=achado["titulo"].strip(),
                    complemento=complemento.strip().lstrip(",").strip(),
                    fim=fim.strip(),
                    bullets=_itens(regiao),
                    solto=LISTA.sub(" ", regiao),
                )
            )
        return tuple(entradas)


@dataclass(frozen=True, slots=True)
class Documento:
    preambulo: str
    corpo: str
    cabecalho: str
    secoes: tuple[Secao, ...]
    fora_das_secoes: str = ""

    def secao(self, titulo: str, config: ConfiguracaoValidador) -> Secao | None:
        alvo = normalizar(titulo)
        return next((s for s in self.secoes if normalizar(plano(s.titulo, config)) == alvo), None)


def ler_documento(tex: str, config: ConfiguracaoValidador) -> Documento:
    limpo = sem_comentarios(tex, config.latex.comentario)
    ambiente = re.escape(config.latex.ambiente_do_corpo)
    inicio = re.search(rf"\\begin\s*\{{{ambiente}\}}", limpo)
    fim = re.search(rf"\\end\s*\{{{ambiente}\}}", limpo)
    if inicio is None:
        return Documento(limpo, "", "", ())
    corpo = limpo[inicio.end() : fim.start() if fim and fim.start() > inicio.end() else None]
    centro = CENTRO.search(corpo)
    partes = SECAO.split(corpo)
    secoes = tuple(Secao(t, c) for t, c in zip(partes[1::2], partes[2::2], strict=True))
    fora = CENTRO.sub(" ", partes[0])
    return Documento(
        limpo[: inicio.start()], corpo, centro.group(1) if centro else "", secoes, fora
    )
