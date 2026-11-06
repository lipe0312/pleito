from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from src.config import carregar
from src.conteudo.modelo import Estrito, Identificador

Simbolo = Annotated[str, StringConstraints(min_length=1, max_length=1)]
Fragmento = Annotated[str, StringConstraints(min_length=1)]


class LatexCorpo(Estrito):
    comandos: list[Identificador]
    ambientes: list[Identificador]
    simbolos: list[Simbolo]


class LatexPreambulo(Estrito):
    comandos: list[Identificador]
    classes: list[Identificador]
    pacotes: list[Identificador]
    definiveis: list[Identificador]
    simbolos: list[Simbolo]


class ConfiguracaoLatex(Estrito):
    comentario: Simbolo
    ambiente_do_corpo: Identificador
    sequencias_proibidas: list[Fragmento]
    esquemas_url: list[Fragmento] = Field(min_length=1)
    corpo: LatexCorpo
    preambulo: LatexPreambulo

    @model_validator(mode="after")
    def _ambiente_do_corpo_e_permitido(self) -> ConfiguracaoLatex:
        if self.ambiente_do_corpo not in self.corpo.ambientes:
            raise ValueError("ambiente_do_corpo precisa estar nos ambientes do corpo")
        return self


class ConfiguracaoCaracteres(Estrito):
    proibidos: list[Simbolo]
    sequencias_proibidas: list[Fragmento]
    categorias_unicode_proibidas: list[Annotated[str, StringConstraints(pattern=r"^[A-Z][a-z]$")]]
    controles_permitidos: list[Simbolo]


class ConfiguracaoValidador(Estrito):
    paginas_max: int = Field(gt=0)
    latex: ConfiguracaoLatex
    caracteres: ConfiguracaoCaracteres
    tecnologias_conhecidas: list[Fragmento]


def configuracao_validador(dados: dict | None = None) -> ConfiguracaoValidador:
    return ConfiguracaoValidador.model_validate(
        dados if dados is not None else carregar("validador")
    )
