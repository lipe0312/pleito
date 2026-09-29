from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
MODELO = Path(__file__).resolve().parent / "templates" / "index.html"
HTMX = Path(__file__).resolve().parent / "static"
app.mount("/assets", StaticFiles(directory=HTMX), name="assets")


@app.get("/", response_class=HTMLResponse)
def inicio() -> HTMLResponse:
    return HTMLResponse(MODELO.read_text(encoding="utf-8"))
