from __future__ import annotations

import re
from collections.abc import Iterable
from functools import cached_property

from pydantic import RootModel

from src.conteudo.modelo import Blocos, Estrito, Identificador, Inventario
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.texto import Palavra, normalizar, palavras, plano

FIM_DE_FRASE = re.compile(r"[.;!?\n]+")


class TermosDoIdioma(Estrito):
    verbos: list[str] = []
    siglas: list[str] = []
    termos: list[str] = []
    projetos: list[str] = []

    @cached_property
    def sequencias(self) -> frozenset[tuple[str, ...]]:
        todos = [*self.verbos, *self.siglas, *self.termos, *self.projetos]
        formas = (tuple(p.forma for p in palavras(texto)) for texto in todos)
        return frozenset(forma for forma in formas if forma)

    def contem(self, termo: str) -> bool:
        return tuple(p.forma for p in palavras(termo)) in self.sequencias

    def cobertura(self, texto: list[Palavra]) -> set[int]:
        formas = [p.forma for p in texto]
        cobertas: set[int] = set()
        for tamanho in {len(sequencia) for sequencia in self.sequencias}:
            for inicio in range(len(formas) - tamanho + 1):
                if tuple(formas[inicio : inicio + tamanho]) in self.sequencias:
                    cobertas.update(range(inicio, inicio + tamanho))
        return cobertas


class Vocabulario(RootModel[dict[Identificador, TermosDoIdioma]]):
    model_config = {"frozen": True}

    def do_idioma(self, idioma: str) -> TermosDoIdioma | None:
        return self.root.get(idioma)


def _frases(textos: Iterable[str], config: ConfiguracaoValidador) -> list[str]:
    frases = []
    for texto in textos:
        for frase in FIM_DE_FRASE.split(plano(texto, config)):
            if frase.strip():
                frases.append(frase.strip())
    return frases


def _textos_do_idioma(blocos: Blocos, idioma: str) -> tuple[list[str], list[str], list[str]]:
    bullets, corridos, nomes = [], [], []
    for bloco in blocos.blocos:
        if idioma in bloco.redacao:
            corridos.append(bloco.redacao[idioma])
        bullets += [b.redacao[idioma] for b in bloco.bullets if idioma in b.redacao]
        if bloco.tipo == "projeto" and idioma in bloco.imutavel.get("nome", {}):
            nomes.append(bloco.imutavel["nome"][idioma])
    return bullets, corridos, nomes


def _siglas(textos: Iterable[str], config: ConfiguracaoValidador) -> set[str]:
    minimo = config.dados.vocabulario.sigla_min_chars
    padrao = re.compile(rf"(?<!\w)[A-Z][A-Z0-9]{{{minimo - 1},}}(?!\w)")
    return {
        normalizar(achado) for texto in textos for achado in padrao.findall(plano(texto, config))
    }


def _termos(frases: list[str], vazias: set[str], config: ConfiguracaoValidador) -> set[str]:
    extracao = config.dados.vocabulario
    achados: set[str] = set()
    for frase in frases:
        formas = [p.forma for p in palavras(frase)]
        for tamanho in range(2, extracao.ngrama_max + 1):
            for inicio in range(len(formas) - tamanho + 1):
                janela = formas[inicio : inicio + tamanho]
                if janela[0] in vazias or janela[-1] in vazias:
                    continue
                termo = " ".join(janela)
                if len(termo) >= extracao.termo_min_chars:
                    achados.add(termo)
    return achados


def _primeiras_palavras(frases: list[str]) -> set[str]:
    return {palavras(frase)[0].forma for frase in frases if palavras(frase)}


def _forma_do_nome(nome: str, config: ConfiguracaoValidador) -> str:
    return " ".join(p.forma for p in palavras(plano(nome, config)))


def _tecnologias_do_dicionario(
    config: ConfiguracaoValidador, inventario: Inventario | None
) -> list[tuple[str, ...]]:
    comuns = {normalizar(nome) for nome in config.tecnologias.palavras_comuns}
    nomes = [*config.tecnologias_conhecidas, *config.dicionario_tecnologias]
    nomes += [e.pedido for e in inventario.equivalencias] if inventario else []
    sequencias = []
    for nome in nomes:
        sequencia = tuple(p.forma for p in palavras(nome))
        if sequencia and normalizar(nome) not in comuns and len("".join(sequencia)) >= 2:
            sequencias.append(sequencia)
    return sequencias


def _com_tecnologia(termo: str, tecnologias: list[tuple[str, ...]]) -> bool:
    formas = tuple(p.forma for p in palavras(termo))
    return any(formas[i : i + len(tec)] == tec for tec in tecnologias for i in range(len(formas)))


def montar_vocabulario(
    blocos: Blocos, config: ConfiguracaoValidador, inventario: Inventario | None = None
) -> Vocabulario:
    tecnologias = _tecnologias_do_dicionario(config, inventario)
    saida: dict[str, TermosDoIdioma] = {}
    for idioma in blocos.idiomas:
        bullets, corridos, nomes = _textos_do_idioma(blocos, idioma)
        vazias = set(config.conteudo.idioma.marcadores.get(idioma, []))
        frases = _frases([*bullets, *corridos], config)
        candidatos = {
            "verbos": _primeiras_palavras(_frases(bullets, config)),
            "siglas": _siglas([*bullets, *corridos], config),
            "termos": _termos(frases, vazias, config),
            "projetos": {_forma_do_nome(nome, config) for nome in nomes if nome},
        }
        saida[idioma] = TermosDoIdioma(
            **{
                grupo: sorted(t for t in termos if not _com_tecnologia(t, tecnologias))
                for grupo, termos in candidatos.items()
            }
        )
    return Vocabulario(saida)
