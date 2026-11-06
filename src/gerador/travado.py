from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.conteudo.arquivo import destino_conteudo
from src.conteudo.configuracao import ConfiguracaoConteudo
from src.conteudo.modelo import Estrito
from src.gerador.configuracao import ConfiguracaoGerador
from src.gerador.erros import SlotInvalido, TravadoInvalido
from src.gerador.escape import LatexSeguro, escapar_latex, texto_limpo, url_segura


class Cabecalho(Estrito):
    nome: str
    email: str
    telefone: str | None = None
    localizacao: dict[str, str]


class Formacao(Estrito):
    instituicao: dict[str, str]
    periodo: str


class Travado(Estrito):
    cabecalho: Cabecalho
    formacao: Formacao


def carregar_travado(
    pasta_dados: Path, config_conteudo: ConfiguracaoConteudo, config: ConfiguracaoGerador
) -> Travado:
    caminho = destino_conteudo(pasta_dados, config_conteudo) / config.travado.arquivo
    try:
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        return Travado.model_validate(bruto)
    except (OSError, yaml.YAMLError, ValidationError) as erro:
        raise TravadoInvalido(f"cabecalho e formacao ilegiveis em {caminho.name}") from erro


def _no_idioma(valores: dict[str, str], idioma: str, nome: str) -> str:
    if idioma not in valores:
        raise TravadoInvalido(f"{nome} sem texto no idioma {idioma!r}")
    return valores[idioma]


def seguro(valor: object, config: ConfiguracaoGerador, nome: str) -> LatexSeguro:
    return LatexSeguro(escapar_latex(texto_limpo(valor, config.travado.texto_max_chars, nome)))


def contexto_travado(travado: Travado, idioma: str, config: ConfiguracaoGerador) -> dict:
    cabecalho = travado.cabecalho
    email = texto_limpo(cabecalho.email, config.travado.texto_max_chars, "email")
    if not re.fullmatch(config.travado.padrao_email, email):
        raise SlotInvalido("email: fora do padrao permitido")
    telefone = None
    if cabecalho.telefone is not None:
        telefone = seguro(cabecalho.telefone, config, "telefone")
    return {
        "cabecalho": {
            "nome": seguro(cabecalho.nome, config, "nome"),
            "email": LatexSeguro(escapar_latex(email)),
            "email_url": LatexSeguro(
                url_segura(f"mailto:{email}", config.travado.padrao_url, "email")
            ),
            "telefone": telefone,
            "localizacao": seguro(
                _no_idioma(cabecalho.localizacao, idioma, "localizacao"), config, "localizacao"
            ),
        },
        "formacao": {
            "instituicao": seguro(
                _no_idioma(travado.formacao.instituicao, idioma, "instituicao"),
                config,
                "instituicao",
            ),
            "periodo": seguro(travado.formacao.periodo, config, "periodo"),
        },
    }
