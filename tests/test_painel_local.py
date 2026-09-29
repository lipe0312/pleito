from __future__ import annotations

import hashlib
from pathlib import Path

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


def test_htmx_vendorizado_tem_hash_fixo():
    arquivo = Path("src/painel/static/htmx.min.js")
    assert arquivo.is_file()
    assert hashlib.sha256(arquivo.read_bytes()).hexdigest() == (
        "d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717"
    )
    assert "npm ci" not in Path("Makefile").read_text(encoding="utf-8")
    assert not Path("package.json").exists()
    assert not Path("package-lock.json").exists()


def test_servidor_painel_usa_somente_loopback(monkeypatch):
    from src.painel import __main__ as painel

    chamadas = []
    monkeypatch.setattr(painel.uvicorn, "run", lambda *args, **kwargs: chamadas.append(kwargs))
    painel.main()
    assert chamadas[0]["host"] == "127.0.0.1"
