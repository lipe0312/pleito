from __future__ import annotations

import re

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.resultado import Regra, Violacao

COMANDO = re.compile(r"\\(?:([A-Za-z]+)|(.)|$)", re.S)
AMBIENTE = re.compile(r"\\(?:begin|end)(?![A-Za-z])")
NOME_DE_AMBIENTE = re.compile(r"\s*\{([^{}]*)\}")
DEFINICAO = re.compile(r"\\newcommand(?![A-Za-z])")
NOME_DEFINIDO = re.compile(r"\s*\{\s*\\([A-Za-z]+)\s*\}")
PACOTE = re.compile(r"\\usepackage(?![A-Za-z])")
CLASSE = re.compile(r"\\documentclass(?![A-Za-z])")
ARGUMENTO_COM_OPCOES = re.compile(r"\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}")
LINK = re.compile(r"\\href(?![A-Za-z])")
DESTINO_DO_LINK = re.compile(r"\s*\{([^{}]*)\}")


def _violacao(detalhe: str) -> Violacao:
    return Violacao(Regra.LATEX, detalhe)


def sem_comentarios(tex: str, comentario: str) -> str:
    padrao = re.compile(rf"\\.|{re.escape(comentario)}[^\n]*", re.S)
    return padrao.sub(lambda m: "" if m.group(0)[0] == comentario else m.group(0), tex)


def _argumentos(
    padrao: re.Pattern[str], argumento: re.Pattern[str], trecho: str
) -> list[str | None]:
    achados = []
    for ocorrencia in padrao.finditer(trecho):
        seguinte = argumento.match(trecho, ocorrencia.end())
        achados.append(seguinte.group(1) if seguinte else None)
    return achados


def _comandos(
    trecho: str, comandos: list[str], simbolos: list[str], ambientes: list[str] | None
) -> list[Violacao]:
    violacoes = []
    for achado in COMANDO.finditer(trecho):
        nome, simbolo = achado.group(1), achado.group(2)
        if nome is not None and nome not in comandos:
            violacoes.append(_violacao(f"comando fora da allowlist: \\{nome}"))
        elif nome is None and (simbolo or "") not in simbolos:
            violacoes.append(_violacao(f"simbolo de controle fora da allowlist: {simbolo!r}"))
    if ambientes is not None:
        for nome in _argumentos(AMBIENTE, NOME_DE_AMBIENTE, trecho):
            if nome is None or nome.strip() not in ambientes:
                violacoes.append(_violacao(f"ambiente fora da allowlist: {nome!r}"))
    return violacoes


def _preambulo(trecho: str, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.latex.preambulo
    violacoes = _comandos(trecho, regras.comandos, regras.simbolos, None)
    for nome in _argumentos(DEFINICAO, NOME_DEFINIDO, trecho):
        if nome not in regras.definiveis:
            violacoes.append(_violacao(f"definicao de comando fora da allowlist: {nome!r}"))
    for argumento in _argumentos(CLASSE, ARGUMENTO_COM_OPCOES, trecho):
        if argumento is None or argumento.strip() not in regras.classes:
            violacoes.append(_violacao(f"classe fora da allowlist: {argumento!r}"))
    for argumento in _argumentos(PACOTE, ARGUMENTO_COM_OPCOES, trecho):
        pacotes = [p.strip() for p in (argumento or "").split(",")]
        fora = [p for p in pacotes if p not in regras.pacotes]
        if argumento is None or fora:
            violacoes.append(_violacao(f"pacote fora da allowlist: {fora or argumento!r}"))
    return violacoes


def _links(trecho: str, config: ConfiguracaoValidador) -> list[Violacao]:
    violacoes = []
    for destino in _argumentos(LINK, DESTINO_DO_LINK, trecho):
        if destino is None or not destino.startswith(tuple(config.latex.esquemas_url)):
            violacoes.append(_violacao(f"endereco de link fora da allowlist: {destino!r}"))
    return violacoes


def _inicio_do_corpo(config: ConfiguracaoValidador) -> re.Pattern[str]:
    return re.compile(rf"\\begin\s*\{{{re.escape(config.latex.ambiente_do_corpo)}\}}")


def corpo_do_tex(tex: str, config: ConfiguracaoValidador) -> str:
    limpo = sem_comentarios(tex, config.latex.comentario)
    marca = _inicio_do_corpo(config).search(limpo)
    return limpo[marca.start() :] if marca else limpo


def validar_latex(tex: str, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.latex
    limpo = sem_comentarios(tex, regras.comentario)
    violacoes = [
        _violacao(f"sequencia proibida: {sequencia!r}")
        for sequencia in regras.sequencias_proibidas
        if sequencia in limpo
    ]
    marcas = list(_inicio_do_corpo(config).finditer(limpo))
    if len(marcas) != 1:
        violacoes.append(_violacao(f"esperado um begin{{{regras.ambiente_do_corpo}}}"))
        corpo = limpo
    else:
        violacoes += _preambulo(limpo[: marcas[0].start()], config)
        corpo = limpo[marcas[0].start() :]
    violacoes += _comandos(
        corpo, regras.corpo.comandos, regras.corpo.simbolos, regras.corpo.ambientes
    )
    violacoes += _links(limpo, config)
    return list(dict.fromkeys(violacoes))
