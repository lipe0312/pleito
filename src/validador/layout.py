from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.conteudo.modelo import Inventario
from src.validador.analise import ContextoConteudo, analisar
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.layout_entrada import EntradaDeLayout, ler_log
from src.validador.layout_limites import validar_limites
from src.validador.layout_log import validar_caixas, validar_compilacao
from src.validador.layout_pdf import validar_sobreposicao, validar_titulo_e_data
from src.validador.resultado import Violacao

FuncaoDeLayout = Callable[[EntradaDeLayout, ConfiguracaoValidador], list[Violacao]]

REGRAS_DE_LAYOUT: tuple[FuncaoDeLayout, ...] = (
    validar_compilacao,
    validar_caixas,
    validar_titulo_e_data,
    validar_sobreposicao,
    validar_limites,
)

__all__ = ["REGRAS_DE_LAYOUT", "EntradaDeLayout", "montar_entrada", "validar_layout"]


def montar_entrada(
    tex: str,
    pdf: Path | None,
    log: Path | None,
    contexto: ContextoConteudo,
    inventario: Inventario,
    config: ConfiguracaoValidador,
) -> EntradaDeLayout:
    if log is None and pdf is not None and pdf.with_suffix(".log").is_file():
        log = pdf.with_suffix(".log")
    return EntradaDeLayout(
        analise=analisar(tex, inventario, contexto, config),
        tex=tex,
        pdf=pdf,
        log=ler_log(log, config) if log is not None else None,
    )


def validar_layout(
    tex: str,
    inventario: Inventario,
    contexto: ContextoConteudo,
    pdf: Path | None,
    log: Path | None,
    config: ConfiguracaoValidador,
) -> list[Violacao]:
    entrada = montar_entrada(tex, pdf, log, contexto, inventario, config)
    violacoes: list[Violacao] = []
    for funcao in REGRAS_DE_LAYOUT:
        violacoes += funcao(entrada, config)
    return list(dict.fromkeys(violacoes))
