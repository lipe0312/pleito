from __future__ import annotations

from dataclasses import dataclass

from src.conteudo.modelo import Blocos, Inventario
from src.gerador.configuracao import configuracao_gerador
from src.gerador.travado import Travado
from src.padroes.configuracao import ConfiguracaoPadroes
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.documento import Documento, Entrada, Secao, ler_documento
from src.validador.texto import plano


@dataclass(frozen=True, slots=True)
class Vaga:
    empresa: str
    descricao: str
    titulo: str = ""


@dataclass(frozen=True, slots=True)
class ContextoConteudo:
    blocos: Blocos
    vaga: Vaga
    padroes: ConfiguracaoPadroes
    travado: Travado
    idioma: str


@dataclass(frozen=True, slots=True)
class Analise:
    documento: Documento
    contexto: ContextoConteudo
    inventario: Inventario
    sobre: Secao | None
    formacao: Secao | None
    experiencias: Secao | None
    projetos: Secao | None

    @property
    def entradas_de_experiencia(self) -> tuple[Entrada, ...]:
        return self.experiencias.entradas() if self.experiencias else ()

    @property
    def entradas_de_projeto(self) -> tuple[Entrada, ...]:
        return self.projetos.entradas() if self.projetos else ()

    @property
    def textos_livres(self) -> tuple[str, ...]:
        textos = [self.sobre.conteudo] if self.sobre else []
        for entrada in (*self.entradas_de_experiencia, *self.entradas_de_projeto):
            textos += entrada.bullets
        return tuple(textos)

    def segmentos(self, config: ConfiguracaoValidador) -> list[str]:
        return [texto for texto in (plano(t, config) for t in self.textos_livres) if texto]


def analisar(
    tex: str,
    inventario: Inventario,
    contexto: ContextoConteudo,
    config: ConfiguracaoValidador,
) -> Analise:
    idioma = contexto.idioma
    if (
        idioma not in contexto.blocos.idiomas
        or idioma not in config.conteudo.secoes
        or idioma not in configuracao_gerador().templates.arquivos
    ):
        raise ValueError(f"idioma sem blocos, secoes ou template: {idioma!r}")
    documento = ler_documento(tex, config)
    titulos = config.conteudo.secoes[idioma]
    return Analise(
        documento=documento,
        contexto=contexto,
        inventario=inventario,
        sobre=documento.secao(titulos.sobre, config),
        formacao=documento.secao(titulos.formacao, config),
        experiencias=documento.secao(titulos.experiencia, config),
        projetos=documento.secao(titulos.projetos, config),
    )
