from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from viabilidade.contratos import Veredito

OVERFULL = re.compile(r"^(Overfull|Underfull) \\[hv]box \((\d+\.?\d*)pt too", re.MULTILINE)
TOLERANCIA_PT = 1.0
COMANDOS_PROIBIDOS = (
    r"\write18",
    r"\input{|",
    r"\openout",
    r"\immediate\write",
    r"\catcode",
    r"\csname",
)


@dataclass(slots=True)
class ResultadoLatex:
    idioma: str
    compilou: bool
    paginas: int | None = None
    overfull_relevantes: list[str] = field(default_factory=list)
    latex_perigoso: list[str] = field(default_factory=list)
    log_erro: str | None = None
    pdf: str | None = None

    def veredito(self) -> Veredito:
        if not self.compilou or self.latex_perigoso:
            return Veredito.NO_GO
        if self.paginas != 1:
            return Veredito.NO_GO
        if self.overfull_relevantes:
            return Veredito.GO_COM_RESSALVA
        return Veredito.GO


def checar_latex_perigoso(tex: str) -> list[str]:
    return [c for c in COMANDOS_PROIBIDOS if c in tex]


def contar_paginas(pdf: Path) -> int | None:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        return len(PdfReader(str(pdf)).pages)
    except (PyPdfError, OSError, ValueError):
        pass
    binario = shutil.which("pdfinfo")
    if binario:
        saida = subprocess.run(
            [binario, str(pdf)], capture_output=True, text=True, check=False
        ).stdout
        for linha in saida.splitlines():
            if linha.startswith("Pages:"):
                return int(linha.split(":")[1].strip())
    return None


def validar_tex(idioma: str, tex: str, guardar_em: Path | None = None) -> ResultadoLatex:
    perigoso = checar_latex_perigoso(tex)
    if perigoso:
        return ResultadoLatex(idioma=idioma, compilou=False, latex_perigoso=perigoso)

    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        return ResultadoLatex(idioma=idioma, compilou=False, log_erro="pdflatex ausente")

    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        fonte = pasta / f"cv_{idioma}.tex"
        fonte.write_text(tex, encoding="utf-8")
        processo = None
        for _ in range(2):
            processo = subprocess.run(
                [
                    pdflatex,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-no-shell-escape",
                    f"-output-directory={pasta}",
                    str(fonte),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if processo.returncode != 0:
                break

        pdf = pasta / f"cv_{idioma}.pdf"
        log = (pasta / f"cv_{idioma}.log").read_text(encoding="utf-8", errors="replace") if (
            pasta / f"cv_{idioma}.log"
        ).exists() else ""

        if processo is None or processo.returncode != 0 or not pdf.exists():
            trecho = "\n".join(
                linha for linha in log.splitlines() if linha.startswith("!")
            )[:2000]
            return ResultadoLatex(idioma=idioma, compilou=False, log_erro=trecho or "falha sem log")

        relevantes = [
            f"{tipo} {excesso}pt"
            for tipo, excesso in OVERFULL.findall(log)
            if float(excesso) > TOLERANCIA_PT
        ]
        destino = None
        if guardar_em is not None:
            guardar_em.mkdir(parents=True, exist_ok=True)
            destino = guardar_em / f"cv_{idioma}.pdf"
            destino.write_bytes(pdf.read_bytes())

        return ResultadoLatex(
            idioma=idioma,
            compilou=True,
            paginas=contar_paginas(pdf),
            overfull_relevantes=relevantes,
            pdf=str(destino) if destino else None,
        )
