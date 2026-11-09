from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from src.config import carregar
from src.painel.app import criar_app
from src.painel.ficticio import ConteudoFicticio, CurriculosFicticio
from src.painel.repositorio import RepositorioFicticio

CONFIG = carregar("painel")
ORIGEM = f"http://127.0.0.1:{CONFIG['porta']}"
CABECALHO = CONFIG["csrf_cabecalho"]
AGORA = datetime(2026, 11, 5, 18, 0, tzinfo=ZoneInfo(CONFIG["fuso"]))
FIXTURE = Path("tests/fixtures/painel_ficticio.yaml")
ATAQUE = "<script>alert("


def relogio() -> datetime:
    return AGORA


def montar(curriculos=None, conteudo=None) -> TestClient:
    aplicacao = criar_app(
        repositorio=RepositorioFicticio.de_dados({}, AGORA),
        relogio=relogio,
        curriculos=curriculos or CurriculosFicticio.de_arquivo(FIXTURE, AGORA),
        conteudo=conteudo or ConteudoFicticio.de_arquivo(FIXTURE),
    )
    return TestClient(aplicacao, base_url=ORIGEM)


def token_da_pagina(cliente: TestClient) -> str:
    pagina = cliente.get("/projetos").text
    return re.search(rf'"{CABECALHO}": "([^"]+)"', pagina).group(1)


def com_token(cliente: TestClient) -> dict[str, str]:
    return {CABECALHO: token_da_pagina(cliente)}
