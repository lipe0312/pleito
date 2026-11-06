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


class ConfiguracaoValidador(Estrito):
    paginas_max: int = Field(gt=0)
    latex: ConfiguracaoLatex
    caracteres: ConfiguracaoCaracteres
    tecnologias_conhecidas: list[Fragmento]


def configuracao_validador(dados: dict | None = None) -> ConfiguracaoValidador:
    return ConfiguracaoValidador.model_validate(
        dados if dados is not None else carregar("validador")
    )
