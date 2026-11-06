from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.config import carregar
from src.painel import __main__ as painel
from src.painel import repositorio as modulo_repositorio

FIXTURE = Path("tests/fixtures/painel_ficticio.yaml")


def test_alvo_do_makefile_sobe_o_painel_com_a_fixture_ficticia():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    alvo = makefile.split("painel-ficticio:")[1].split("\n\n")[0]
    assert "src.painel" in alvo
    assert "--ficticio" in alvo
    assert str(FIXTURE) in alvo
    assert "painel-ficticio" in makefile.split(".PHONY:")[1].split("\n")[0]


def test_painel_ficticio_sobe_sem_abrir_conexao_com_o_banco(monkeypatch):
    chamadas = []
    monkeypatch.setattr(painel.uvicorn, "run", lambda *args, **kwargs: chamadas.append(kwargs))

    def proibida(componente):
        raise AssertionError("o painel fictício não pode tocar o banco")

    monkeypatch.setattr(modulo_repositorio, "conectar", proibida)
    painel.main(["--ficticio", str(FIXTURE)])
    configuracao = carregar("painel")
    assert chamadas[0]["host"] == configuracao["host_bind"] == "127.0.0.1"
    assert chamadas[0]["port"] == configuracao["porta"]


def test_painel_ficticio_serve_as_duas_telas_sem_banco(monkeypatch):
    from fastapi.testclient import TestClient

    aplicacoes = []
    monkeypatch.setattr(painel.uvicorn, "run", lambda app, **kwargs: aplicacoes.append(app))
    monkeypatch.setattr(
        modulo_repositorio, "conectar", lambda componente: pytest.fail("tocou o banco")
    )
    painel.main(["--ficticio", str(FIXTURE)])
    origem = f"http://127.0.0.1:{carregar('painel')['porta']}"
    cliente = TestClient(aplicacoes[0], base_url=origem)
    assert cliente.get("/hoje").status_code == 200
    assert cliente.get("/candidaturas").status_code == 200


def test_fixture_ficticia_nao_tem_dado_pessoal_nem_dominio_real():
    texto = FIXTURE.read_text(encoding="utf-8")
    for endereco in re.findall(r"[\w.+-]+@([\w.-]+)", texto):
        assert endereco.endswith(".example")


def test_sem_argumento_o_painel_usa_o_banco(monkeypatch):
    chamadas = []
    monkeypatch.setattr(painel.uvicorn, "run", lambda app, **kwargs: chamadas.append(app))
    painel.main()
    assert chamadas[0] is painel.app
