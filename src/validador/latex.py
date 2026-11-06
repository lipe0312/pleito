from __future__ import annotations

import re
from urllib.parse import urlsplit

from src.validador.configuracao import ConfiguracaoValidador, Medidas
from src.validador.resultado import Regra, Violacao

COMANDO = re.compile(r"\\(?:([A-Za-z]+)|(.)|$)", re.S)
AMBIENTE = re.compile(r"\\(?:begin|end)(?![A-Za-z])")
NOME_DE_AMBIENTE = re.compile(r"\s*\{([^{}]*)\}")
DEFINICAO = re.compile(r"\\newcommand(?![A-Za-z])")
NOME_DEFINIDO = re.compile(r"\*?\s*\{\s*\\([A-Za-z]+)\s*\}")
PACOTE = re.compile(r"\\usepackage(?![A-Za-z])")
CLASSE = re.compile(r"\\documentclass(?![A-Za-z])")
ARGUMENTO_COM_OPCOES = re.compile(r"\s*(?:\[([^\]]*)\])?\s*\{([^{}]*)\}")
GRUPO = re.compile(r"\s*\{([^{}]*)\}")
MEDIDA = re.compile(r"\s*(-?(?:\d+\.?\d*|\.\d+))\s*([a-z]+)\s*")
COMANDO_SOZINHO = re.compile(r"\s*\\[A-Za-z]+\s*")
LINK = re.compile(r"\\href(?![A-Za-z])")
DESTINO_DO_LINK = re.compile(r"\s*\{([^{}]*)\}")


def _violacao(detalhe: str) -> Violacao:
    return Violacao(Regra.LATEX, detalhe)


def sem_comentarios(tex: str, comentario: str) -> str:
    padrao = re.compile(rf"\\.|{re.escape(comentario)}[^\n]*(?:\n[ \t]*)?", re.S)
    return padrao.sub(lambda m: "" if m.group(0)[0] == comentario else m.group(0), tex)


def _argumentos(
    padrao: re.Pattern[str], argumento: re.Pattern[str], trecho: str
) -> list[tuple[str | None, ...] | None]:
    achados = []
    for ocorrencia in padrao.finditer(trecho):
        seguinte = argumento.match(trecho, ocorrencia.end())
        achados.append(seguinte.groups() if seguinte else None)
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
        for grupos in _argumentos(AMBIENTE, NOME_DE_AMBIENTE, trecho):
            nome = grupos[0] if grupos else None
            if nome is None or nome.strip() not in ambientes:
                violacoes.append(_violacao(f"ambiente fora da allowlist: {nome!r}"))
    return violacoes


def _opcoes_fora(opcoes: str | None, padroes: list[str]) -> list[str]:
    if opcoes is None:
        return []
    return [
        opcao
        for opcao in (o.strip() for o in opcoes.split(","))
        if not any(re.fullmatch(padrao, opcao) for padrao in padroes)
    ]


def _preambulo(trecho: str, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.latex.preambulo
    violacoes = _comandos(trecho, regras.comandos, regras.simbolos, None)
    for grupos in _argumentos(DEFINICAO, NOME_DEFINIDO, trecho):
        nome = grupos[0] if grupos else None
        if nome not in regras.definiveis:
            violacoes.append(_violacao(f"definicao de comando fora da allowlist: {nome!r}"))
    for grupos in _argumentos(CLASSE, ARGUMENTO_COM_OPCOES, trecho):
        nome = grupos[1].strip() if grupos else None
        if nome not in regras.classes:
            violacoes.append(_violacao(f"classe fora da allowlist: {nome!r}"))
            continue
        fora = _opcoes_fora(grupos[0], regras.classes[nome])
        violacoes += [_violacao(f"opcao de classe fora da allowlist: {o!r}") for o in fora]
    for grupos in _argumentos(PACOTE, ARGUMENTO_COM_OPCOES, trecho):
        if grupos is None:
            violacoes.append(_violacao("usepackage mal formado"))
            continue
        for nome in (p.strip() for p in grupos[1].split(",")):
            if nome not in regras.pacotes:
                violacoes.append(_violacao(f"pacote fora da allowlist: {nome!r}"))
                continue
            fora = _opcoes_fora(grupos[0], regras.pacotes[nome])
            violacoes += [_violacao(f"opcao de {nome} fora da allowlist: {o!r}") for o in fora]
    return violacoes


def _dominio_permitido(hospedeiro: str, dominios: list[str]) -> bool:
    return any(hospedeiro == d or hospedeiro.endswith(f".{d}") for d in dominios)


def _endereco_permitido(destino: str, config: ConfiguracaoValidador) -> bool:
    regras = config.latex.links
    if destino.startswith(tuple(regras.esquemas_sem_dominio)):
        return True
    try:
        partes = urlsplit(destino)
        hospedeiro = partes.hostname
        porta = partes.port
    except ValueError:
        return False
    return (
        partes.scheme == regras.esquema_seguro
        and hospedeiro is not None
        and porta is None
        and partes.username is None
        and partes.password is None
        and _dominio_permitido(hospedeiro.lower(), [d.lower() for d in regras.dominios])
    )


def _links(trecho: str, config: ConfiguracaoValidador) -> list[Violacao]:
    violacoes = []
    for grupos in _argumentos(LINK, DESTINO_DO_LINK, trecho):
        destino = grupos[0] if grupos else None
        if destino is None or not _endereco_permitido(destino, config):
            violacoes.append(_violacao(f"endereco de link fora da allowlist: {destino!r}"))
    return violacoes


def _medida_valida(argumento: str, regras: Medidas) -> bool:
    if COMANDO_SOZINHO.fullmatch(argumento):
        return True
    achado = MEDIDA.fullmatch(argumento)
    if achado is None or achado.group(2) not in regras.unidades_mm:
        return False
    milimetros = float(achado.group(1)) * regras.unidades_mm[achado.group(2)]
    return regras.minimo_mm <= milimetros <= regras.maximo_mm


def _medidas(trecho: str, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.latex.medidas
    violacoes = []
    for nome, total in regras.comandos.items():
        for ocorrencia in re.finditer(rf"\\{re.escape(nome)}(?![A-Za-z])\*?", trecho):
            posicao, argumentos = ocorrencia.end(), []
            for _ in range(total):
                grupo = GRUPO.match(trecho, posicao)
                if grupo is None:
                    break
                argumentos.append(grupo.group(1))
                posicao = grupo.end()
            if len(argumentos) != total:
                violacoes.append(_violacao(f"medida mal formada em \\{nome}"))
            violacoes += [
                _violacao(f"medida fora do limite em \\{nome}: {a.strip()!r}")
                for a in argumentos
                if not _medida_valida(a, regras)
            ]
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
    violacoes += _medidas(limpo, config)
    return list(dict.fromkeys(violacoes))
