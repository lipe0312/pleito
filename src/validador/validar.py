from __future__ import annotations

from pathlib import Path

from src.conteudo.modelo import Inventario
from src.validador import niveis
from src.validador.analise import ContextoConteudo
from src.validador.banco import BancoTecnologias
from src.validador.caracteres import validar_alfabeto, validar_invisiveis, validar_travessao
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador
from src.validador.conteudo import validar_conteudo
from src.validador.latex import validar_latex
from src.validador.layout import validar_layout
from src.validador.paginas import texto_do_pdf, validar_paginas
from src.validador.resultado import CurriculoInvalido, Regra, Resultado, Violacao
from src.validador.tecnologias import validar_tecnologias, validar_tecnologias_no_texto
from src.validador.vocabulario import TermosDoIdioma


def _resultado(violacoes: list[Violacao], config: ConfiguracaoValidador) -> Resultado:
    return Resultado(tuple(dict.fromkeys(niveis.aplicar_niveis(violacoes, config))))


def validar_fonte(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    *,
    banco: BancoTecnologias | None = None,
    vocabulario: TermosDoIdioma | None = None,
) -> Resultado:
    config = config or configuracao_validador()
    violacoes: list[Violacao] = []
    violacoes += validar_latex(tex, config)
    violacoes += validar_invisiveis(tex, config)
    violacoes += validar_alfabeto(tex, config)
    violacoes += validar_travessao(tex, config)
    violacoes += validar_tecnologias(tex, inventario, config, banco, vocabulario)
    return _resultado(violacoes, config)


def validar_arquivos(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    pdf: Path | None = None,
    *,
    banco: BancoTecnologias | None = None,
    vocabulario: TermosDoIdioma | None = None,
) -> Resultado:
    config = config or configuracao_validador()
    violacoes = list(
        validar_fonte(tex, inventario, config, banco=banco, vocabulario=vocabulario).violacoes
    )
    if pdf is None:
        violacoes.append(Violacao(Regra.PAGINAS, "pdf ausente, paginas nao conferidas"))
    else:
        texto = texto_do_pdf(pdf)
        violacoes += validar_paginas(pdf, config)
        violacoes += validar_alfabeto(texto, config)
        violacoes += validar_travessao(texto, config)
        violacoes += validar_tecnologias_no_texto(texto, inventario, config, banco, vocabulario)
    return _resultado(violacoes, config)


def validar_curriculo(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    pdf: Path | None = None,
    *,
    contexto: ContextoConteudo,
    log: Path | None = None,
) -> Resultado:
    config = config or configuracao_validador()
    violacoes = list(
        validar_arquivos(
            tex,
            inventario,
            config,
            pdf,
            banco=contexto.banco,
            vocabulario=contexto.termos_do_vocabulario,
        ).violacoes
    )
    violacoes += validar_conteudo(tex, inventario, contexto, config)
    violacoes += validar_layout(tex, inventario, contexto, pdf, log, config)
    return _resultado(violacoes, config)


def exigir_fonte_valida(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    *,
    banco: BancoTecnologias | None = None,
    vocabulario: TermosDoIdioma | None = None,
) -> None:
    resultado = validar_fonte(tex, inventario, config, banco=banco, vocabulario=vocabulario)
    if not resultado.aprovado:
        raise CurriculoInvalido(resultado)


def exigir_arquivos_validos(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    pdf: Path | None = None,
    *,
    banco: BancoTecnologias | None = None,
    vocabulario: TermosDoIdioma | None = None,
) -> None:
    resultado = validar_arquivos(tex, inventario, config, pdf, banco=banco, vocabulario=vocabulario)
    if not resultado.aprovado:
        raise CurriculoInvalido(resultado)


def exigir_valido(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador | None = None,
    pdf: Path | None = None,
    *,
    contexto: ContextoConteudo,
    log: Path | None = None,
) -> None:
    resultado = validar_curriculo(tex, inventario, config, pdf, contexto=contexto, log=log)
    if not resultado.aprovado:
        raise CurriculoInvalido(resultado)
