from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from src.config import carregar
from src.conteudo.modelo import Estrito, Identificador

Simbolo = Annotated[str, StringConstraints(min_length=1, max_length=1)]
Fragmento = Annotated[str, StringConstraints(min_length=1)]


class LatexCorpo(Estrito):
    comandos: list[Identificador]
    ambientes: list[Identificador]
    simbolos: list[Simbolo]


def _padroes_compilam(opcoes: dict[str, list[str]]) -> dict[str, list[str]]:
    for padroes in opcoes.values():
        for padrao in padroes:
            re.compile(padrao)
    return opcoes


OpcoesPermitidas = Annotated[
    dict[Identificador, list[Fragmento]], AfterValidator(_padroes_compilam)
]


class LatexPreambulo(Estrito):
    comandos: list[Identificador]
    classes: OpcoesPermitidas
    pacotes: OpcoesPermitidas
    definiveis: list[Identificador]
    simbolos: list[Simbolo]


class Links(Estrito):
    esquema_seguro: Identificador
    dominios: list[Fragmento] = Field(min_length=1)
    esquemas_sem_dominio: list[Fragmento]


class Medidas(Estrito):
    comandos: dict[Identificador, int]
    minimo_mm: float
    maximo_mm: float = Field(gt=0)
    unidades_mm: dict[Identificador, float]

    @model_validator(mode="after")
    def _faixa_e_comandos_validos(self) -> Medidas:
        if self.minimo_mm > self.maximo_mm:
            raise ValueError("minimo_mm maior que maximo_mm")
        if any(total < 1 for total in self.comandos.values()):
            raise ValueError("comando de medida precisa de ao menos um argumento")
        return self


class ConfiguracaoLatex(Estrito):
    comentario: Simbolo
    ambiente_do_corpo: Identificador
    sequencias_proibidas: list[Fragmento]
    links: Links
    medidas: Medidas
    corpo: LatexCorpo
    preambulo: LatexPreambulo

    @model_validator(mode="after")
    def _ambiente_do_corpo_e_permitido(self) -> ConfiguracaoLatex:
        if self.ambiente_do_corpo not in self.corpo.ambientes:
            raise ValueError("ambiente_do_corpo precisa estar nos ambientes do corpo")
        return self


class Alfabeto(Estrito):
    scripts: list[Annotated[str, StringConstraints(pattern=r"^[A-Z]+$")]] = Field(min_length=1)
    scripts_com_base_ascii: list[Annotated[str, StringConstraints(pattern=r"^[A-Z]+$")]]
    extras: list[Simbolo]


class ConfiguracaoCaracteres(Estrito):
    proibidos: list[Simbolo]
    sequencias_proibidas: list[Fragmento]
    categorias_unicode_proibidas: list[Annotated[str, StringConstraints(pattern=r"^[A-Z][a-z]$")]]
    controles_permitidos: list[Simbolo]
    alfabeto: Alfabeto


def _regexes_compilam(padroes: list[str]) -> list[str]:
    for padrao in padroes:
        try:
            re.compile(padrao)
        except re.error as erro:
            raise ValueError(f"regex invalida: {padrao!r}") from erro
    return padroes


PorIdioma = dict[Identificador, list[Fragmento]]


class PreambuloDoConteudo(Estrito):
    parametros_livres: Annotated[list[Fragmento], AfterValidator(_regexes_compilam)]


class ProjetosDoConteudo(Estrito):
    minimo: int = Field(ge=1)
    maximo: int = Field(ge=1)
    rotulo_final: dict[Identificador, Fragmento] = Field(min_length=1)

    @model_validator(mode="after")
    def _minimo_nao_passa_do_maximo(self) -> ProjetosDoConteudo:
        if self.minimo > self.maximo:
            raise ValueError("minimo de projetos maior que o maximo")
        return self


class CopiaDaVaga(Estrito):
    palavras: int = Field(ge=2)


class EmpresaDaVaga(Estrito):
    tamanho_minimo: int = Field(ge=1)
    sufixos: list[Fragmento]


class Negrito(Estrito):
    comandos: list[Identificador] = Field(min_length=1)


class Escapes(Estrito):
    simbolos: list[Simbolo] = Field(min_length=1)


class IdiomaDoConteudo(Estrito):
    marcadores: PorIdioma = Field(min_length=2)


class SecoesDoIdioma(Estrito):
    sobre: Fragmento
    formacao: Fragmento
    experiencia: Fragmento
    projetos: Fragmento


class ConfiguracaoDoConteudo(Estrito):
    trecho_max_chars: int = Field(gt=0)
    secoes: dict[Identificador, SecoesDoIdioma] = Field(min_length=1)
    preambulo: PreambuloDoConteudo
    projetos: ProjetosDoConteudo
    copia_da_vaga: CopiaDaVaga
    empresa_da_vaga: EmpresaDaVaga
    negrito: Negrito
    escapes: Escapes
    idioma: IdiomaDoConteudo

    @model_validator(mode="after")
    def _mesmos_idiomas_em_tudo(self) -> ConfiguracaoDoConteudo:
        idiomas = set(self.secoes)
        if set(self.projetos.rotulo_final) != idiomas or set(self.idioma.marcadores) != idiomas:
            raise ValueError("secoes, rotulo_final e marcadores precisam dos mesmos idiomas")
        return self


class ConfiguracaoValidador(Estrito):
    paginas_max: int = Field(gt=0)
    latex: ConfiguracaoLatex
    caracteres: ConfiguracaoCaracteres
    tecnologias_conhecidas: list[Fragmento]
    conteudo: ConfiguracaoDoConteudo


def configuracao_validador(dados: dict | None = None) -> ConfiguracaoValidador:
    return ConfiguracaoValidador.model_validate(
        dados if dados is not None else carregar("validador")
    )
