from __future__ import annotations

from fastapi.testclient import TestClient

from src.painel.app import app


def test_painel_abre_uma_pagina_vazia_sem_operacoes():
    cliente = TestClient(app)
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert "Pleito" in resposta.text
    assert "Candidaturas" not in resposta.text
    assert "/assets/htmx.min.js" in resposta.text
    assert cliente.get("/assets/htmx.min.js").status_code == 200


def test_servidor_painel_usa_somente_loopback(monkeypatch):
    from src.painel import __main__ as painel

    chamadas = []
    monkeypatch.setattr(painel.uvicorn, "run", lambda *args, **kwargs: chamadas.append(kwargs))
    painel.main()
    assert chamadas[0]["host"] == "127.0.0.1"
