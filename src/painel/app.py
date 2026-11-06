from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.config import carregar
from src.painel.renderizar import renderizar
from src.painel.seguranca import ProtecaoPainel, gerar_token

MODELO = Path(__file__).resolve().parent / "templates" / "index.html"
ESTATICOS = Path(__file__).resolve().parent / "static"


def criar_app() -> FastAPI:
    token = gerar_token()
    cabecalho = carregar("painel")["csrf_cabecalho"]
    aplicacao = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    aplicacao.mount("/assets", StaticFiles(directory=ESTATICOS), name="assets")

    @aplicacao.get("/", response_class=HTMLResponse)
    def inicio() -> HTMLResponse:
        pagina = renderizar(
            MODELO.read_text(encoding="utf-8"), csrf_cabecalho=cabecalho, csrf_token=token
        )
        return HTMLResponse(pagina)

    aplicacao.add_middleware(ProtecaoPainel, token=token)
    return aplicacao


app = criar_app()
