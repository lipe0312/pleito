from __future__ import annotations

import os
import re
from pathlib import Path

PADRAO_GUIA = "../base/guia-adaptacao-curriculo-filipe-santana.md"
GUIA = Path(os.getenv("PLEITO_GUIA", Path(__file__).resolve().parents[2] / PADRAO_GUIA)).resolve()

BLOCO = re.compile(r"```(?:latex|tex)?\s*\n(\\documentclass.*?\\end\{document\})", re.DOTALL)
ABERTURA = re.compile(r"\\documentclass.*", re.DOTALL)

CORRECOES = (
    (re.compile(r"\\tech\{([^}]*?)(?<!\\)_([^}]*?)\}"), r"\\tech{\1\\_\2}"),
    (re.compile(r"^#+\s*(\\end\{document\})", re.MULTILINE), r"\1"),
)


def aplicar_correcoes(tex: str) -> tuple[str, list[str]]:
    aplicadas = []
    for padrao, troca in CORRECOES:
        tex, n = padrao.subn(troca, tex)
        if n:
            aplicadas.append(f"{padrao.pattern} x{n}")
    return tex, aplicadas


def _fatiar(markdown: str) -> list[str]:
    achados = BLOCO.findall(markdown)
    if achados:
        return achados
    pedacos = []
    for trecho in ABERTURA.findall(markdown):
        for parte in trecho.split("\\documentclass"):
            if not parte.strip():
                continue
            corpo = "\\documentclass" + parte
            fim = corpo.find("\\end{document}")
            if fim != -1:
                pedacos.append(corpo[: fim + len("\\end{document}")])
    return pedacos


def extrair_bases(guia: Path = GUIA, destino: Path | None = None) -> dict[str, dict]:
    markdown = guia.read_text(encoding="utf-8")
    blocos = _fatiar(markdown)
    if len(blocos) < 2:
        raise ValueError(f"esperava 2 curriculos base no guia, achei {len(blocos)}")

    saida: dict[str, dict] = {}
    for idioma, bruto in zip(("pt", "en"), blocos[:2], strict=False):
        tex, aplicadas = aplicar_correcoes(bruto.strip())
        registro = {"tex": tex, "correcoes": aplicadas, "caminho": None}
        if destino is not None:
            destino.mkdir(parents=True, exist_ok=True)
            arquivo = destino / f"cv_{idioma}.tex"
            arquivo.write_text(tex + "\n", encoding="utf-8")
            registro["caminho"] = str(arquivo)
        saida[idioma] = registro
    return saida
