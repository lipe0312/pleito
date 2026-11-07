from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.validador.analise import Analise
from src.validador.configuracao import ConfiguracaoValidador


@dataclass(frozen=True, slots=True)
class LeituraDoLog:
    linhas: tuple[str, ...]
    problema: str


@dataclass(frozen=True, slots=True)
class EntradaDeLayout:
    analise: Analise
    tex: str
    pdf: Path | None
    log: LeituraDoLog | None


def ler_log(caminho: Path, config: ConfiguracaoValidador) -> LeituraDoLog:
    limite = config.layout.log.tamanho_max_bytes
    try:
        with caminho.open("rb") as arquivo:
            bruto = arquivo.read(limite + 1)
    except OSError:
        return LeituraDoLog((), "log ausente ou ilegivel")
    if len(bruto) > limite:
        return LeituraDoLog((), f"log maior que {limite} bytes")
    return LeituraDoLog(tuple(bruto.decode("utf-8", "replace").splitlines()), "")
