from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from viabilidade.contratos import Funcao, ModeloTrabalho, Senioridade, VagaBruta

ENDERECOS_LOCAIS = {"127.0.0.1", "localhost", "::1"}
MARCADORES_COM_REDE = {"rede", "navegador"}


class RedeBloqueada(AssertionError):
    pass


@pytest.fixture(autouse=True)
def bloquear_rede_externa(request, monkeypatch):
    if MARCADORES_COM_REDE & {m.name for m in request.node.iter_markers()}:
        return
    original = socket.socket.connect

    def conectar_local(self, endereco):
        if isinstance(endereco, tuple) and endereco[0] in ENDERECOS_LOCAIS:
            return original(self, endereco)
        if not isinstance(endereco, tuple):
            return original(self, endereco)
        raise RedeBloqueada(f"teste padrao tentou rede externa: {endereco[0]}")

    monkeypatch.setattr(socket.socket, "connect", conectar_local)


@pytest.fixture
def vaga_completa() -> VagaBruta:
    return VagaBruta(
        fonte="greenhouse",
        id_externo="123",
        url="https://boards.greenhouse.io/nubank/jobs/123",
        titulo="Software Engineer Intern",
        empresa="nubank",
        descricao="x" * 400,
        local="Sao Paulo, Brazil",
        pais="BR",
        senioridade=Senioridade.ESTAGIO,
        modelo=ModeloTrabalho.REMOTO,
        funcao=Funcao.ENGENHARIA,
        anos_experiencia=1,
    )


@pytest.fixture
def fixtures() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def banco():
    if os.getenv("PLEITO_TEST_DATABASE") != "1":
        pytest.skip("testes de banco nao solicitados")
    host = os.getenv("POSTGRES_HOST")
    port = int(os.getenv("POSTGRES_PORT", "0"))
    dbname = os.getenv("POSTGRES_DB")
    if host not in {"127.0.0.1", "localhost"} or port != 55432:
        pytest.fail(
            "testes de banco so podem conectar ao Postgres isolado do pleito na porta 55432"
        )
    if dbname != "pleito":
        pytest.fail("testes de banco so podem conectar ao banco pleito")
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    ) as conexao:
        yield conexao
