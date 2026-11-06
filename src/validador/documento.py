from __future__ import annotations

import re
from dataclasses import dataclass

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.latex import sem_comentarios
from src.validador.texto import normalizar, plano

SECAO = re.compile(r"\\section\*?\{((?:[^{}\\]|\\.)*)\}")
CENTRO = re.compile(r"\\begin\s*\{center\}(.*?)\\end\s*\{center\}", re.S)
ENTRADA = re.compile(
    r"^[ \t]*\\textbf\{(?P<titulo>(?:[^{}\\]|\\.)*)\}"
    r"(?P<complemento>[^\n]*?)\\hfill(?P<fim>[^\n]*)$",
    re.M,
)
LISTA = re.compile(r"\s*\\begin\{itemize\}(?P<itens>.*?)\\end\{itemize\}", re.S)
ITEM = re.compile(r"\\item(?![A-Za-z])")


@dataclass(frozen=True, slots=True)
class Entrada:
    titulo: str
    complemento: str
    fim: str
    bullets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Secao:
    titulo: str
    conteudo: str

    def entradas(self) -> tuple[Entrada, ...]:
        achados = list(ENTRADA.finditer(self.conteudo))
        entradas = []
        for posicao, achado in enumerate(achados):
            limite = achados[posicao + 1].start() if posicao + 1 < len(achados) else None
            lista = LISTA.match(self.conteudo[achado.end() : limite])
            itens = ITEM.split(lista["itens"]) if lista else []
            entradas.append(
                Entrada(
                    titulo=achado["titulo"].strip(),
                    complemento=achado["complemento"].strip(),
                    fim=achado["fim"].strip(),
                    bullets=tuple(" ".join(item.split()) for item in itens if item.strip()),
                )
            )
        return tuple(entradas)


@dataclass(frozen=True, slots=True)
class Documento:
    preambulo: str
    corpo: str
    cabecalho: str
    secoes: tuple[Secao, ...]

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
    return Documento(limpo[: inicio.start()], corpo, centro.group(1) if centro else "", secoes)
