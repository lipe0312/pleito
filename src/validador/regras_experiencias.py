from __future__ import annotations

from src.conteudo.modelo import Bloco
from src.validador.analise import Analise
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.resultado import Regra, Violacao
from src.validador.texto import normalizar, plano, violacao


def _campo(bloco: Bloco, campo: str, idioma: str) -> str:
    return bloco.imutavel.get(campo, {}).get(idioma, "")


def _chave(titulo: str, periodo: str, config: ConfiguracaoValidador) -> tuple[str, str]:
    return normalizar(plano(titulo, config)), normalizar(plano(periodo, config))


def _esperadas(analise: Analise, config: ConfiguracaoValidador) -> list[tuple[str, str, str]]:
    idioma = analise.contexto.idioma
    esperadas = []
    for bloco in analise.contexto.blocos.blocos:
        if bloco.tipo != "experiencia":
            continue
        titulo = f"{_campo(bloco, 'cargo', idioma)}, {_campo(bloco, 'empresa', idioma)}"
        esperadas.append(
            (
                plano(titulo, config),
                plano(_campo(bloco, "periodo", idioma), config),
                plano(_campo(bloco, "empresa", idioma), config),
            )
        )
    return esperadas


def validar_experiencias(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    if analise.experiencias is None:
        return []
    esperadas = _esperadas(analise, config)
    chaves = [_chave(titulo, periodo, config) for titulo, periodo, _ in esperadas]
    violacoes = []
    posicoes = []
    for entrada in analise.entradas_de_experiencia:
        chave = _chave(entrada.titulo, entrada.fim, config)
        if chave in chaves:
            posicoes.append(chaves.index(chave))
            continue
        titulo = plano(f"{entrada.titulo} {entrada.fim}", config)
        parecida = next(
            (
                e
                for e in esperadas
                if normalizar(e[2]) in normalizar(titulo) or normalizar(e[1]) == chave[1]
            ),
            None,
        )
        sugestao = (
            f"use exatamente '{parecida[0]}' e '{parecida[1]}' do bloco"
            if parecida
            else "remova a experiencia que nao esta nos blocos"
        )
        violacoes.append(
            violacao(
                config, Regra.EXPERIENCIAS, "experiencia diferente dos blocos", titulo, sugestao
            )
        )
    if posicoes != sorted(set(posicoes)):
        violacoes.append(
            violacao(
                config,
                Regra.EXPERIENCIAS,
                "experiencias repetidas ou fora da ordem dos blocos",
                " > ".join(plano(e.titulo, config) for e in analise.entradas_de_experiencia),
                "mantenha a ordem cronologica dos blocos, sem repetir",
            )
        )
    violacoes += [
        violacao(
            config,
            Regra.EXPERIENCIAS,
            "experiencia dos blocos ausente",
            esperadas[posicao][0],
            "inclua a experiencia; nunca remova uma experiencia",
        )
        for posicao in range(len(esperadas))
        if posicao not in posicoes
    ]
    return violacoes


def validar_experiencias_vazias(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    return [
        violacao(
            config,
            Regra.EXPERIENCIA_VAZIA,
            "experiencia sem bullet",
            plano(entrada.titulo, config),
            "escreva ao menos um bullet para a experiencia",
        )
        for entrada in analise.entradas_de_experiencia
        if not entrada.bullets
    ]


def validar_projetos(analise: Analise, config: ConfiguracaoValidador) -> list[Violacao]:
    regras = config.conteudo.projetos
    rotulo = normalizar(regras.rotulo_final[analise.contexto.idioma])
    entradas = analise.entradas_de_projeto
    titulos = [normalizar(plano(e.titulo, config)) for e in entradas]
    projetos = [t for t in titulos if t != rotulo]
    violacoes = []
    if not regras.minimo <= len(projetos) <= regras.maximo:
        violacoes.append(
            violacao(
                config,
                Regra.PROJETOS,
                f"{len(projetos)} projetos, esperado de {regras.minimo} a {regras.maximo}",
                ", ".join(projetos),
                f"deixe de {regras.minimo} a {regras.maximo} projetos dos blocos",
            )
        )
    if rotulo in titulos and titulos[-1] != rotulo:
        violacoes.append(
            violacao(
                config,
                Regra.PROJETOS,
                "mais projetos nao e o ultimo",
                regras.rotulo_final[analise.contexto.idioma],
                "mova o item de mais projetos para o fim da secao",
            )
        )
    return violacoes
