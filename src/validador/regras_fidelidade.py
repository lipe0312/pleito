from __future__ import annotations

import re

from src.padroes.pontuacao import violacoes_de_pontuacao
from src.validador.analise import Analise, ContextoConteudo
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.resultado import Regra, Violacao
from src.validador.texto import (
    Palavra,
    ao_redor,
    ocorrencias,
    palavras,
    plano,
    violacao,
)

NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


def _canonico(numero: str) -> str:
    return numero.replace(",", ".")


def _fatos_fixos(contexto: ContextoConteudo, config: ConfiguracaoValidador) -> list[str]:
    textos = []
    for bloco in contexto.blocos.blocos:
        textos += [t for por_idioma in bloco.imutavel.values() for t in por_idioma.values()]
    cabecalho = contexto.travado.cabecalho
    textos += [cabecalho.nome, cabecalho.email, cabecalho.telefone or ""]
    textos += list(cabecalho.localizacao.values())
    textos += list(contexto.travado.formacao.instituicao.values())
    textos.append(contexto.travado.formacao.periodo)
    return [plano(t, config) for t in textos if t]


def _fatos_livres(analise: Analise) -> list[str]:
    textos = []
    for bloco in analise.contexto.blocos.blocos:
        textos += list(bloco.redacao.values())
        textos += [t for bullet in bloco.bullets for t in bullet.redacao.values()]
    textos += [item.tech for item in analise.inventario.techs]
    return textos


def validar_numeros(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    fatos = _fatos_fixos(analise.contexto, config)
    fatos += [plano(t, config) for t in _fatos_livres(analise)]
    conhecidos = {_canonico(n) for texto in fatos for n in NUMERO.findall(texto)}
    texto = plano(analise.documento.corpo, config)
    violacoes = []
    vistos: set[str] = set()
    for achado in NUMERO.finditer(texto):
        numero = _canonico(achado.group(0))
        if numero in conhecidos or numero in vistos:
            continue
        vistos.add(numero)
        violacoes.append(
            violacao(
                config,
                Regra.NUMERO,
                f"numero fora dos blocos: {achado.group(0)}",
                ao_redor(texto, achado.start(), achado.end(), config),
                "tire o numero; so valem numeros que estao nos blocos",
            )
        )
    return violacoes


def _nome_da_empresa(empresa: str, config: ConfiguracaoValidador) -> list[str]:
    nome = [p.forma for p in palavras(empresa)]
    sufixos = [[p.forma for p in palavras(s)] for s in config.conteudo.empresa_da_vaga.sufixos]
    mudou = True
    while mudou:
        mudou = False
        for sufixo in sufixos:
            if sufixo and len(nome) > len(sufixo) and nome[-len(sufixo) :] == sufixo:
                nome = nome[: -len(sufixo)]
                mudou = True
    return nome


def _cobertas(texto: list[Palavra], fatos: list[str]) -> set[int]:
    cobertas: set[int] = set()
    for fato in fatos:
        sequencia = [p.forma for p in palavras(fato)]
        for inicio in ocorrencias(texto, sequencia):
            cobertas.update(range(inicio, inicio + len(sequencia)))
    return cobertas


def validar_empresa_da_vaga(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.conteudo.empresa_da_vaga
    nome = _nome_da_empresa(analise.contexto.vaga.empresa, config)
    if len(" ".join(nome)) < regras.tamanho_minimo:
        return []
    texto = plano(analise.documento.corpo, config)
    formas = palavras(texto)
    cobertas = _cobertas(formas, _fatos_fixos(analise.contexto, config))
    violacoes = []
    for inicio in ocorrencias(formas, nome):
        janela = range(inicio, inicio + len(nome))
        if cobertas.intersection(janela):
            continue
        violacoes.append(
            violacao(
                config,
                Regra.EMPRESA_DA_VAGA,
                "nome da empresa da vaga no curriculo",
                ao_redor(texto, formas[inicio].inicio, formas[janela[-1]].fim, config),
                "tire o nome da empresa da vaga; descreva so o que esta nos blocos",
            )
        )
    return violacoes


def _janelas(formas: list[Palavra], tamanho: int) -> list[tuple[str, ...]]:
    return [
        tuple(p.forma for p in formas[i : i + tamanho]) for i in range(len(formas) - tamanho + 1)
    ]


def validar_copia_da_vaga(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    tamanho = config.conteudo.copia_da_vaga.palavras
    anuncio = set(_janelas(palavras(analise.contexto.vaga.descricao), tamanho))
    violacoes = []
    for segmento in analise.segmentos(config):
        formas = palavras(segmento)
        iguais = [i for i, janela in enumerate(_janelas(formas, tamanho)) if janela in anuncio]
        while iguais:
            primeiro = ultimo = iguais[0]
            while ultimo + 1 in iguais:
                ultimo += 1
            iguais = [i for i in iguais if i > ultimo]
            violacoes.append(
                violacao(
                    config,
                    Regra.COPIA_DA_VAGA,
                    f"trecho de {tamanho} palavras ou mais copiado do anuncio",
                    segmento[formas[primeiro].inicio : formas[ultimo + tamanho - 1].fim],
                    "reescreva com suas palavras, partindo do que esta nos blocos",
                )
            )
    return violacoes


def validar_pontuacao(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    padroes = analise.contexto.padroes
    violacoes = []
    for segmento in analise.segmentos(config):
        for achado in violacoes_de_pontuacao(padroes, segmento):
            if achado == "terminador":
                sugestao = f"termine o texto com '{padroes.pontuacao.terminador_bullet}'"
            else:
                sugestao = (
                    f"tire o caractere; separe ideias com '{padroes.pontuacao.separador_interno}'"
                )
            violacoes.append(
                violacao(config, Regra.PONTUACAO, f"pontuacao: {achado}", segmento, sugestao)
            )
    return violacoes


def validar_senioridade(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    inflada = analise.contexto.padroes.senioridade_inflada
    idioma = analise.contexto.idioma
    termos = [*inflada.verbos[idioma], *inflada.expressoes[idioma]]
    base = [p.forma for p in palavras(" ".join(plano(t, config) for t in _fatos_livres(analise)))]
    base += [p.forma for p in palavras(" ".join(_fatos_fixos(analise.contexto, config)))]
    violacoes = []
    for termo in termos:
        sequencia = [p.forma for p in palavras(termo)]
        if ocorrencias([Palavra(f, 0, 0) for f in base], sequencia):
            continue
        for segmento in analise.segmentos(config):
            if ocorrencias(palavras(segmento), sequencia):
                violacoes.append(
                    violacao(
                        config,
                        Regra.SENIORIDADE,
                        f"senioridade sem base nos blocos: {termo}",
                        segmento,
                        f"tire '{termo}'; o nivel vem dos blocos",
                    )
                )
                break
    return violacoes
