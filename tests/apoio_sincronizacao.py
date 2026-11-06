from __future__ import annotations

import copy
from datetime import UTC, datetime

import httpx
import respx

from src.coletor.conformidade import Limitador
from src.config import carregar
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.sincronizacao import configuracao_sincronizacao
from src.conteudo.sincronizar import sincronizar

USUARIO = "usuario-ficticio"
API = "https://api.github.com"
REPO_URL = f"https://github.com/{USUARIO}"
PORTFOLIO = "https://portfolio-ficticio.example"
AGORA = datetime(2030, 1, 10, 12, 0, tzinfo=UTC)


def dados_config(**ajustes) -> dict:
    dados = copy.deepcopy(carregar("conteudo"))
    sinc = dados["sincronizacao"]
    sinc["github"]["usuario"] = USUARIO
    sinc["portfolio"]["dominios"] = ["portfolio-ficticio.example"]
    for caminho, valor in ajustes.items():
        alvo = sinc
        *pais, folha = caminho.split(".")
        for parte in pais:
            alvo = alvo[parte]
        alvo[folha] = valor
    return dados


def repositorio(nome="ficticio-api", **campos) -> dict:
    base = {
        "name": nome,
        "description": "api de exemplo",
        "topics": ["spring"],
        "homepage": None,
        "pushed_at": "2029-12-01T10:00:00Z",
        "fork": False,
        "archived": False,
        "private": False,
        "language": "Java",
    }
    base.update(campos)
    return base


def montar_github(
    roteador: respx.MockRouter,
    repos: list[dict],
    linguagens: dict[str, dict] | None = None,
    readmes: dict[str, str] | None = None,
) -> None:
    linguagens = linguagens or {}
    readmes = readmes or {}
    roteador.get(f"{API}/users/{USUARIO}/repos").mock(return_value=httpx.Response(200, json=repos))
    for repo in repos:
        nome = repo["name"]
        if nome not in linguagens and nome not in readmes:
            continue
        roteador.get(f"{API}/repos/{USUARIO}/{nome}/languages").mock(
            return_value=httpx.Response(200, json=linguagens.get(nome, {}))
        )
        texto = readmes.get(nome)
        resposta = (
            httpx.Response(200, text=texto, headers={"content-type": "text/plain"})
            if texto is not None
            else httpx.Response(404)
        )
        roteador.get(f"{API}/repos/{USUARIO}/{nome}/readme").mock(return_value=resposta)


def rodar(pasta_dados, dados=None, client=None):
    config = configuracao_sincronizacao(dados or dados_config())
    with client or httpx.Client() as cliente:
        return sincronizar(
            config,
            configuracao_conteudo(),
            pasta_dados,
            cliente,
            Limitador(0),
            AGORA,
        )


def por_tipo(resultado, tipo):
    return [s for s in resultado.sugestoes if s.tipo == tipo]


def techs(resultado) -> set[str]:
    return {s.tech for s in por_tipo(resultado, "tecnologia_nova")}
