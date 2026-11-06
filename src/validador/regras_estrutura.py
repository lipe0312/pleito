from __future__ import annotations

import re

from src.config import RAIZ
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.decompor import BABEL, TECH
from src.gerador.configuracao import configuracao_gerador
from src.validador.analise import Analise
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.latex import sem_comentarios
from src.validador.resultado import Regra, Violacao
from src.validador.texto import (
    DESTINO_DO_LINK,
    ao_redor,
    normalizar,
    palavras,
    plano,
    violacao,
)


def _linhas_do_preambulo(texto: str, config: ConfiguracaoValidador) -> list[str]:
    for padrao in config.conteudo.preambulo.parametros_livres:
        texto = re.sub(padrao, "", texto)
    return [" ".join(linha.split()) for linha in texto.splitlines() if linha.strip()]


def _preambulo_do_template(idioma: str, config: ConfiguracaoValidador) -> str:
    templates = configuracao_gerador().templates
    fonte = (RAIZ / templates.pasta / templates.arquivos[idioma]).read_text(encoding="utf-8")
    limpo = sem_comentarios(fonte, config.latex.comentario)
    ambiente = re.escape(config.latex.ambiente_do_corpo)
    marca = re.search(rf"\\begin\s*\{{{ambiente}\}}", limpo)
    return limpo[: marca.start()] if marca else limpo


def validar_preambulo(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    idioma = analise.contexto.idioma
    esperado = _linhas_do_preambulo(_preambulo_do_template(idioma, config), config)
    atual = _linhas_do_preambulo(analise.documento.preambulo, config)
    if atual == esperado:
        return []
    a_mais = next((linha for linha in atual if linha not in esperado), None)
    a_menos = next((linha for linha in esperado if linha not in atual), None)
    trecho = a_mais or (f"falta: {a_menos}" if a_menos else "ordem das linhas")
    return [
        violacao(
            config,
            Regra.PREAMBULO,
            f"preambulo diferente do template de {idioma}",
            trecho,
            "restaure o preambulo do template; so linespread e margens podem variar",
        )
    ]


def validar_cabecalho(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    travado = analise.contexto.travado
    idioma = analise.contexto.idioma
    cabecalho = travado.cabecalho
    esperados = {"nome": cabecalho.nome, "email": cabecalho.email}
    if cabecalho.telefone:
        esperados["telefone"] = cabecalho.telefone
    if cabecalho.localizacao.get(idioma):
        esperados["cidade"] = cabecalho.localizacao[idioma]
    texto = plano(analise.documento.cabecalho, config)
    restante = normalizar(texto)
    violacoes = []
    for campo, valor in esperados.items():
        alvo = normalizar(plano(valor, config))
        if alvo not in restante:
            violacoes.append(
                violacao(
                    config,
                    Regra.CABECALHO,
                    f"cabecalho sem {campo} igual ao base",
                    texto,
                    f"use exatamente o {campo} do base",
                )
            )
        restante = restante.replace(alvo, " ")
    sobra = " ".join(re.sub(r"[\W_]+", " ", restante).split())
    if sobra:
        violacoes.append(
            violacao(
                config,
                Regra.CABECALHO,
                "texto extra no cabecalho",
                sobra,
                "deixe no cabecalho so nome, cidade, email e telefone do base",
            )
        )
    permitidos = {f"{e}{cabecalho.email}" for e in config.latex.links.esquemas_sem_dominio}
    violacoes += [
        violacao(
            config,
            Regra.CABECALHO,
            "link do cabecalho diferente do base",
            destino,
            "use apenas o link de email do base",
        )
        for destino in dict.fromkeys(DESTINO_DO_LINK.findall(analise.documento.cabecalho))
        if destino not in permitidos
    ]
    if analise.formacao is not None:
        formacao = normalizar(plano(analise.formacao.conteudo, config))
        base = {
            "instituicao": travado.formacao.instituicao.get(idioma, ""),
            "periodo": travado.formacao.periodo,
        }
        violacoes += [
            violacao(
                config,
                Regra.CABECALHO,
                f"formacao sem {campo} igual ao base",
                plano(analise.formacao.conteudo, config),
                f"use exatamente o {campo} do base",
            )
            for campo, valor in base.items()
            if normalizar(plano(valor, config)) not in formacao
        ]
    return violacoes


def validar_estrutura(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    idioma = analise.contexto.idioma
    esperadas = [normalizar(t) for t in config.conteudo.secoes[idioma].model_dump().values()]
    proibidas = {normalizar(t) for t in analise.contexto.padroes.secoes_proibidas}
    originais = [plano(s.titulo, config) for s in analise.documento.secoes]
    titulos = [normalizar(titulo) for titulo in originais]
    violacoes = []
    for original, titulo in zip(originais, titulos, strict=True):
        if titulo in proibidas:
            violacoes.append(
                violacao(config, Regra.ESTRUTURA, "secao proibida", original, "remova a secao")
            )
        elif titulo not in esperadas:
            violacoes.append(
                violacao(
                    config,
                    Regra.ESTRUTURA,
                    "secao nova",
                    original,
                    "use so as secoes do template, na ordem",
                )
            )
    violacoes += [
        violacao(
            config,
            Regra.ESTRUTURA,
            "secao ausente",
            esperada,
            "inclua a secao do template",
        )
        for esperada in esperadas
        if esperada not in titulos
    ]
    conhecidas = [t for t in titulos if t in esperadas]
    if conhecidas != [e for e in esperadas if e in conhecidas]:
        violacoes.append(
            violacao(
                config,
                Regra.ESTRUTURA,
                "secoes repetidas ou fora de ordem",
                " > ".join(titulos),
                f"siga a ordem {' > '.join(esperadas)}",
            )
        )
    comandos = "|".join(re.escape(c) for c in config.conteudo.negrito.comandos)
    negrito = re.compile(rf"\\(?:{comandos})(?![A-Za-z])")
    for texto in analise.textos_livres:
        sem_tech = TECH.sub(lambda achado: " " * len(achado.group(0)), texto)
        for achado in negrito.finditer(sem_tech):
            violacoes.append(
                violacao(
                    config,
                    Regra.ESTRUTURA,
                    "negrito fora de tech",
                    ao_redor(texto, achado.start(), achado.end(), config),
                    "tire o negrito; so \\tech{} pode destacar",
                )
            )
    return violacoes


def validar_escapes(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    simbolos = "".join(re.escape(s) for s in config.conteudo.escapes.simbolos)
    padrao = re.compile(rf"(?<!\\)(?:\\\\)*(?P<simbolo>[{simbolos}])")
    corpo = DESTINO_DO_LINK.sub(lambda achado: " " * len(achado.group(0)), analise.documento.corpo)
    return [
        violacao(
            config,
            Regra.ESCAPE,
            f"simbolo sem escape: {achado['simbolo']}",
            ao_redor(corpo, achado.start("simbolo"), achado.end("simbolo"), config),
            f"escreva \\{achado['simbolo']} no lugar de {achado['simbolo']}",
        )
        for achado in padrao.finditer(corpo)
    ]


def _marcadores(texto: str, config: ConfiguracaoValidador) -> dict[str, int]:
    formas = [p.forma for p in palavras(texto)]
    return {
        idioma: sum(1 for forma in formas if forma in conhecidos)
        for idioma, conhecidos in _formas_conhecidas(config).items()
    }


def _formas_conhecidas(config: ConfiguracaoValidador) -> dict[str, set[str]]:
    return {
        idioma: {normalizar(m) for m in lista}
        for idioma, lista in config.conteudo.idioma.marcadores.items()
    }


def validar_idioma(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    idioma = analise.contexto.idioma
    nomes = config.conteudo.idioma.nomes
    violacoes = []
    babel = BABEL.search(analise.documento.preambulo)
    declarado = None
    if babel:
        opcao = babel.group(1).split(",")[-1].strip()
        declarado = configuracao_conteudo().idiomas_babel.get(opcao)
    if declarado != idioma:
        esperada = next(
            (o for o, i in configuracao_conteudo().idiomas_babel.items() if i == idioma), idioma
        )
        violacoes.append(
            violacao(
                config,
                Regra.IDIOMA,
                f"babel declara {declarado or 'idioma desconhecido'}, esperado {idioma}",
                babel.group(0) if babel else "sem babel",
                f"use o babel {esperada}, do idioma {nomes[idioma]}",
            )
        )
    for segmento in analise.segmentos(config):
        contagem = _marcadores(segmento, config)
        outros = [i for i in contagem if i != idioma and contagem[i] > contagem[idioma]]
        if outros:
            outro = max(outros, key=contagem.get)
            violacoes.append(
                violacao(
                    config,
                    Regra.IDIOMA,
                    f"texto parece estar em {nomes[outro]}, esperado {nomes[idioma]}",
                    segmento,
                    f"reescreva o texto em {nomes[idioma]}",
                )
            )
    return violacoes
