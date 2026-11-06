from __future__ import annotations

from pathlib import Path

from src.conteudo.modelo import Inventario
from src.validador.caracteres import validar_alfabeto, validar_invisiveis, validar_travessao
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador
from src.validador.latex import validar_latex
from src.validador.paginas import texto_do_pdf, validar_paginas
from src.validador.resultado import CurriculoInvalido, Regra, Resultado, Violacao
from src.validador.tecnologias import validar_tecnologias, validar_tecnologias_no_texto


def validar_fonte(
    tex: str, inventario: Inventario, config: ConfiguracaoValidador | None = None
) -> Resultado:
    config = config or configuracao_validador()
    violacoes: list[Violacao] = []
    violacoes += validar_latex(tex, config)
    violacoes += validar_invisiveis(tex, config)
    violacoes += validar_alfabeto(tex, config)
    violacoes += validar_travessao(tex, config)
    violacoes += validar_tecnologias(tex, inventario, config)
    return Resultado(tuple(dict.fromkeys(violacoes)))


def validar_curriculo(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    pdf: Path | None = None,
) -> Resultado:
    config = config or configuracao_validador()
    violacoes = list(validar_fonte(tex, inventario, config).violacoes)
    if pdf is None:
        violacoes.append(Violacao(Regra.PAGINAS, "pdf ausente, paginas nao conferidas"))
    else:
        texto = texto_do_pdf(pdf)
        violacoes += validar_paginas(pdf, config)
        violacoes += validar_alfabeto(texto, config)
        violacoes += validar_travessao(texto, config)
        violacoes += validar_tecnologias_no_texto(texto, inventario, config)
    return Resultado(tuple(dict.fromkeys(violacoes)))


def exigir_fonte_valida(
    tex: str, inventario: Inventario, config: ConfiguracaoValidador | None = None
) -> None:
    resultado = validar_fonte(tex, inventario, config)
    if not resultado.aprovado:
        raise CurriculoInvalido(resultado)


def exigir_valido(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    pdf: Path | None = None,
) -> None:
    resultado = validar_curriculo(tex, inventario, config, pdf)
    if not resultado.aprovado:
        raise CurriculoInvalido(resultado)
