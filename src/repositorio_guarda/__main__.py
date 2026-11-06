from __future__ import annotations

import sys

from src.config import carregar
from src.repositorio_guarda.guarda import (
    Achado,
    verificar_arquivos,
    verificar_diff,
    verificar_mensagem,
)

TITULOS = {
    "arquivos": "commit recusado: arquivo proibido no indice",
    "diff": "commit recusado: padrao de segredo nas linhas adicionadas",
    "mensagem": "commit recusado: a mensagem tem atribuicao a ferramenta",
}


def relatar(modo: str, achados: list[Achado]) -> int:
    if not achados:
        return 0
    print(TITULOS[modo], file=sys.stderr)
    for achado in achados:
        print(f"  {achado.onde}  [{achado.regra}]", file=sys.stderr)
    return 1


def principal(argumentos: list[str]) -> int:
    regras = carregar("repositorio")
    modo = argumentos[0] if argumentos else ""
    if modo == "arquivos":
        return relatar(modo, verificar_arquivos(regras["caminhos"]))
    if modo == "diff":
        return relatar(modo, verificar_diff(regras["segredos"]))
    if modo == "mensagem" and len(argumentos) == 2:
        return relatar(modo, verificar_mensagem(argumentos[1], regras["atribuicao"]))
    print("uso: repositorio_guarda arquivos | diff | mensagem <arquivo>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
