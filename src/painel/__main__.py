from __future__ import annotations

import uvicorn

from src.config import carregar
from src.painel.app import app


def main() -> None:
    configuracao = carregar("painel")
    uvicorn.run(app, host=configuracao["host_bind"], port=int(configuracao["porta"]))


if __name__ == "__main__":
    main()
