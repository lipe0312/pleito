from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.conteudo.modelo import Inventario
from src.validador.analise import ContextoConteudo, analisar
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.geometria import PdfIlegivel, ler_geometria
from src.validador.layout_entrada import EntradaDeLayout, LeituraDoLog, ler_log
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
    geometria, falha = None, ""
    if pdf is not None:
        try:
            geometria = ler_geometria(pdf, config)
        except PdfIlegivel as erro:
            falha = str(erro)
    return EntradaDeLayout(
        analise=analisar(tex, inventario, contexto, config),
        tex=tex,
        pdf=pdf,
        log=_log_valido(pdf, log, config),
        geometria=geometria,
        falha_da_geometria=falha,
    )


def _log_valido(pdf: Path | None, log: Path | None, config: ConfiguracaoValidador):
    if pdf is None and log is None:
        return None
    caminho = log if log is not None else pdf.with_suffix(".log")
    leitura = ler_log(caminho, config)
    if leitura.problema or pdf is None:
        return leitura
    try:
        defasagem = pdf.stat().st_mtime - caminho.stat().st_mtime
    except OSError:
        return leitura
    if defasagem > config.layout.log.defasagem_max_s:
        return LeituraDoLog((), "log do pdflatex mais velho que o pdf")
    return leitura


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
