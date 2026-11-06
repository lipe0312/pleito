from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from src.config import carregar
from src.painel.app import criar_app
from src.painel.repositorio import RepositorioFicticio

ORIGEM = f"http://127.0.0.1:{carregar('painel')['porta']}"
AGORA = datetime(2026, 11, 5, 18, 0, tzinfo=ZoneInfo(carregar("painel")["fuso"]))


def test_painel_serve_o_htmx_local_e_as_telas_apontam_para_ele():
    repositorio = RepositorioFicticio.de_dados({}, AGORA)
    cliente = TestClient(criar_app(repositorio=repositorio), base_url=ORIGEM)
    resposta = cliente.get("/hoje")
    assert resposta.status_code == 200
    assert "Pleito" in resposta.text
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
    configuracao = carregar("painel")
    assert chamadas[0]["host"] == configuracao["host_bind"] == "127.0.0.1"
    assert chamadas[0]["port"] == configuracao["porta"]
    assert chamadas[0].get("workers", 1) == 1
    assert not chamadas[0].get("reload", False)


def test_bind_e_porta_vem_da_config(monkeypatch):
    from src.painel import __main__ as painel

    chamadas = []
    monkeypatch.setattr(painel.uvicorn, "run", lambda *args, **kwargs: chamadas.append(kwargs))
    monkeypatch.setattr(
        painel, "carregar", lambda nome: {"host_bind": "127.0.0.2", "porta": 9999}
    )
    painel.main()
    assert (chamadas[0]["host"], chamadas[0]["port"]) == ("127.0.0.2", 9999)
