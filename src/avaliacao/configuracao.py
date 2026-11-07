from __future__ import annotations

from typing import Annotated

from pydantic import Field

from src.config import carregar
from src.conteudo.modelo import Estrito, Identificador, TextoNaoVazio


class Armadilhas(Estrito):
    pasta: TextoNaoVazio
    guia: TextoNaoVazio
    travado: TextoNaoVazio


class VagasReais(Estrito):
    subpasta: TextoNaoVazio
    tipo: Identificador


class Relatorios(Estrito):
    subpasta: TextoNaoVazio


class Offline(Estrito):
    tokens_entrada: int = Field(ge=0)
    tokens_saida: int = Field(ge=0)


class Caso(Estrito):
    executor: Identificador
    tarefa: Identificador
    armadilhas: list[Identificador] = []
    vagas_reais: bool = False


class ConfiguracaoAvaliacao(Estrito):
    versao_conjunto: int = Field(ge=1)
    armadilhas: Armadilhas
    vagas_reais: VagasReais
    relatorios: Relatorios
    taxa_minima_aprovacao: float = Field(ge=0, le=1)
    regras_fora: list[Identificador] = []
    offline: Offline
    casos: Annotated[dict[Identificador, Caso], Field(min_length=1)]


def configuracao_avaliacao(dados: dict | None = None) -> ConfiguracaoAvaliacao:
    return ConfiguracaoAvaliacao.model_validate(
        dados if dados is not None else carregar("avaliacao")
    )
