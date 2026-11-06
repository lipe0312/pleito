from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from pypdf import PdfReader

from src.gerador.configuracao import ConfiguracaoGerador

LINHAS_DO_ERRO = 15


class MotorAusente(RuntimeError):
    pass


class CompilacaoFalhou(RuntimeError):
    pass


class PaginasDemais(RuntimeError):
    pass


def compilar(tex: str, pasta: Path, config: ConfiguracaoGerador) -> Path:
    opcoes = config.compilacao
    motor = shutil.which(opcoes.motor)
    if motor is None:
        raise MotorAusente(f"{opcoes.motor} nao encontrado")
    pasta.mkdir(parents=True, exist_ok=True)
    fonte = pasta / f"{opcoes.nome_arquivo}.tex"
    pdf = pasta / f"{opcoes.nome_arquivo}.pdf"
    pdf.unlink(missing_ok=True)
    fonte.write_text(tex, encoding="utf-8")
    try:
        resultado = subprocess.run(
            [motor, *opcoes.argumentos, fonte.name],
            cwd=pasta,
            env=os.environ | opcoes.ambiente,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=opcoes.timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as erro:
        raise CompilacaoFalhou(f"{opcoes.motor} passou de {opcoes.timeout_s}s") from erro
    if resultado.returncode != 0 or not pdf.is_file():
        fim = resultado.stdout.decode("utf-8", "replace").splitlines()[-LINHAS_DO_ERRO:]
        raise CompilacaoFalhou("\n".join(fim))
    paginas = len(PdfReader(pdf).pages)
    if paginas > opcoes.paginas_max:
        raise PaginasDemais(f"{paginas} paginas, limite {opcoes.paginas_max}")
    return pdf
