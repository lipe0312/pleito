from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.resultado import Regra, Violacao


def ler_pdf(pdf: Path) -> PdfReader | None:
    try:
        return PdfReader(pdf)
    except (OSError, PyPdfError, ValueError):
        return None


def validar_paginas(pdf: Path, config: ConfiguracaoValidador) -> list[Violacao]:
    leitor = ler_pdf(pdf)
    if leitor is None:
        return [Violacao(Regra.PAGINAS, "pdf ausente ou ilegivel")]
    try:
        total = len(leitor.pages)
    except (PyPdfError, ValueError):
        return [Violacao(Regra.PAGINAS, "pdf ilegivel")]
    if total > config.paginas_max:
        return [Violacao(Regra.PAGINAS, f"{total} paginas, limite {config.paginas_max}")]
    return []


def texto_do_pdf(pdf: Path) -> str:
    leitor = ler_pdf(pdf)
    if leitor is None:
        return ""
    try:
        return "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    except (PyPdfError, ValueError):
        return ""
