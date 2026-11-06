from __future__ import annotations

import re
from typing import Annotated

from pydantic import StringConstraints, field_validator

from src.config import carregar
from src.conteudo.modelo import Estrito, TextoNaoVazio

UsuarioGithub = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")]


class Tecnologia(Estrito):
    tech: TextoNaoVazio
    linguagens: list[str] = []
    topics: list[str] = []
    termos: list[str] = []
    requer: list[str] = []


class FonteGithub(Estrito):
    usuario: UsuarioGithub
    api: TextoNaoVazio
    url_publica: TextoNaoVazio
    dominios: list[str]
    respeitar_robots: bool
    ignorar_fork: bool
    ignorar_arquivado: bool
    por_pagina: int
    paginas_max: int
    readme_max_chars: int
    topics_max: int
    topic_padrao: TextoNaoVazio
    linguagem_max_chars: int
    nome_repositorio_padrao: TextoNaoVazio
    cabecalho_json: dict[str, str]
    cabecalho_readme: dict[str, str]


class PaginaPortfolio(Estrito):
    url: TextoNaoVazio
    nome: TextoNaoVazio


class FontePortfolio(Estrito):
    dominios: list[str]
    respeitar_robots: bool
    pagina_max_chars: int
    paginas: list[PaginaPortfolio]


class ConfiguracaoSincronizacao(Estrito):
    arquivo_sugestoes: TextoNaoVazio
    prefixo_id_projeto: TextoNaoVazio
    descricao_max_chars: int
    requisicoes_max: int
    resposta_max_bytes: int
    tipos_conteudo_aceitos: list[str]
    github: FonteGithub
    portfolio: FontePortfolio
    padroes_instrucao: list[re.Pattern[str]]
    dicionario: list[Tecnologia]

    @field_validator("padroes_instrucao", mode="before")
    @classmethod
    def _compilar(cls, valor: list[str]) -> list[re.Pattern[str]]:
        return [re.compile(padrao, re.IGNORECASE) for padrao in valor]


def configuracao_sincronizacao(dados: dict | None = None) -> ConfiguracaoSincronizacao:
    bruto = dados if dados is not None else carregar("conteudo")
    return ConfiguracaoSincronizacao.model_validate(
        {**bruto["sincronizacao"], "arquivo_sugestoes": bruto["destino"]["sugestoes"]}
    )
