from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn

from src.config import carregar
from src.painel.app import app, criar_app
from src.painel.repositorio import RepositorioFicticio


def _argumentos(argv: Sequence[str]) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(prog="painel")
    analisador.add_argument("--ficticio", type=Path, default=None)
    return analisador.parse_args(list(argv))


def main(argv: Sequence[str] = ()) -> None:
    configuracao = carregar("painel")
    argumentos = _argumentos(argv)
    aplicacao = app
    if argumentos.ficticio is not None:
        agora = datetime.now(ZoneInfo(configuracao["fuso"]))
        repositorio = RepositorioFicticio.de_arquivo(argumentos.ficticio, agora)
        aplicacao = criar_app(repositorio=repositorio)
    uvicorn.run(aplicacao, host=configuracao["host_bind"], port=int(configuracao["porta"]))


if __name__ == "__main__":
    main(sys.argv[1:])
