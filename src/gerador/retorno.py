from __future__ import annotations

from src.gerador.configuracao import ConfiguracaoGerador
from src.padroes.configuracao import ConfiguracaoPadroes
from src.validador.resultado import Violacao


def neutralizar(texto: str, padroes: ConfiguracaoPadroes) -> str:
    marcacao = padroes.marcacao
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = texto.replace(marcacao.abre, marcacao.neutro).replace(
            marcacao.fecha, marcacao.neutro
        )
    return texto


def marcado(texto: str, limite: int, padroes: ConfiguracaoPadroes) -> str:
    corpo = neutralizar(" ".join(texto.split())[:limite], padroes)
    return f"{padroes.marcacao.abre}\n{corpo}\n{padroes.marcacao.fecha}"


def codigo_da_violacao(violacao: Violacao) -> str:
    return violacao.codigo or str(violacao.regra)


def retorno_de_violacoes(
    violacoes: tuple[Violacao, ...], config: ConfiguracaoGerador, padroes: ConfiguracaoPadroes
) -> str:
    retorno = config.laco.retorno
    linhas = [retorno.violacoes]
    for violacao in violacoes[: retorno.violacoes_max]:
        codigo = codigo_da_violacao(violacao)
        descricao = retorno.regras.get(codigo, "")
        linha = f"- {codigo}: {descricao}" if descricao else f"- {codigo}"
        if violacao.trecho:
            linha += "\n" + marcado(violacao.trecho, retorno.trecho_max_chars, padroes)
        linhas.append(linha)
    return "\n\n".join(linhas)


def retorno_de_descarte(
    erro: str, config: ConfiguracaoGerador, padroes: ConfiguracaoPadroes
) -> str:
    retorno = config.laco.retorno
    return f"{retorno.descartada}\n{marcado(erro, retorno.trecho_max_chars, padroes)}"


def retorno_de_melhoria(
    fracos: list[str], config: ConfiguracaoGerador, padroes: ConfiguracaoPadroes
) -> str:
    criterios = padroes.rubrica.criterios
    linhas = [config.laco.retorno.melhoria]
    linhas += [f"- {criterios[nome].descricao}" for nome in fracos if nome in criterios]
    return "\n\n".join(linhas)


def retorno_de_refacao(
    motivo: str, config: ConfiguracaoGerador, padroes: ConfiguracaoPadroes
) -> str:
    return f"{config.laco.retorno.refacao}\n\n{neutralizar(motivo, padroes)}"
