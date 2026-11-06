from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.config import carregar
from src.db.conexao import ConfiguracaoBancoInvalida
from src.painel.repositorio import RepositorioBanco, RepositorioFicticio, RepositorioLeitura
from src.painel.seguranca import ProtecaoPainel, gerar_token
from src.painel.telas import Contexto, pagina_candidaturas, pagina_erro, pagina_hoje

ESTATICOS = Path(__file__).resolve().parent / "static"
FALHAS_DE_LEITURA = (psycopg.Error, ConfiguracaoBancoInvalida)


def _relogio_padrao() -> datetime:
    return datetime.now(ZoneInfo(carregar("painel")["fuso"]))


def criar_app(
    repositorio: RepositorioLeitura | None = None,
    relogio: Callable[[], datetime] | None = None,
) -> FastAPI:
    configuracao = carregar("painel")
    token = gerar_token(configuracao["token_bytes"])
    leitura = repositorio if repositorio is not None else RepositorioBanco()
    ficticio = isinstance(leitura, RepositorioFicticio)
    agora = relogio or _relogio_padrao
    aplicacao = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    aplicacao.mount("/assets", StaticFiles(directory=ESTATICOS), name="assets")

    def contexto() -> Contexto:
        return Contexto(
            csrf_cabecalho=configuracao["csrf_cabecalho"],
            csrf_token=token,
            ficticio=ficticio,
            agora=agora(),
        )

    def responder(montar: Callable[[RepositorioLeitura, Contexto], str]) -> HTMLResponse:
        atual = contexto()
        try:
            return HTMLResponse(montar(leitura, atual))
        except FALHAS_DE_LEITURA:
            return HTMLResponse(pagina_erro(atual), status_code=503)

    @aplicacao.get("/")
    def inicio() -> RedirectResponse:
        return RedirectResponse(configuracao["rota_inicial"], status_code=303)

    @aplicacao.get("/hoje", response_class=HTMLResponse)
    def hoje() -> HTMLResponse:
        return responder(pagina_hoje)

    @aplicacao.get("/candidaturas", response_class=HTMLResponse)
    def candidaturas() -> HTMLResponse:
        return responder(pagina_candidaturas)

    aplicacao.add_middleware(ProtecaoPainel, token=token)
    return aplicacao


app = criar_app()
