from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from src.config import RAIZ, ambiente
from src.conteudo.arquivo import gravar
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.decompor import decompor


def executar(variaveis: Mapping[str, str], pasta_dados: Path, raiz: Path) -> int:
    config = configuracao_conteudo()
    bruto = variaveis.get(config.variavel_guia, "").strip()
    if not bruto:
        print(f"defina {config.variavel_guia} com o caminho do guia", file=sys.stderr)
        return 2
    caminho = Path(bruto).expanduser()
    caminho = caminho if caminho.is_absolute() else raiz / caminho
    if not caminho.is_file():
        print(f"{config.variavel_guia} aponta para arquivo inexistente: {caminho}", file=sys.stderr)
        return 2
    try:
        blocos, inventario = decompor(caminho.read_text(encoding="utf-8"), config)
        caminho_blocos, caminho_inventario = gravar(blocos, inventario, pasta_dados, config)
    except ValueError as erro:
        print(f"guia recusado: {erro}", file=sys.stderr)
        return 1
    total_bullets = sum(len(bloco.bullets) for bloco in blocos.blocos)
    print(
        f"{len(blocos.blocos)} blocos, {total_bullets} bullets, "
        f"{len(inventario.techs)} techs e {len(inventario.equivalencias)} equivalencias"
    )
    print(f"gravado em {caminho_blocos} e {caminho_inventario}")
    return 0


def main() -> None:
    raise SystemExit(executar(os.environ, ambiente().dados, RAIZ))


if __name__ == "__main__":
    main()
