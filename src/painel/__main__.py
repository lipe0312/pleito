from __future__ import annotations

import uvicorn

from src.painel.app import app
from viabilidade.config import carregar


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=int(carregar("painel")["porta"]))


if __name__ == "__main__":
    main()
