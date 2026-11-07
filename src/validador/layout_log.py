from __future__ import annotations

import re

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.layout_entrada import EntradaDeLayout
from src.validador.resultado import Regra, Violacao
from src.validador.texto import recorte, violacao

ERRO = "!"
OVERFULL = re.compile(r"^Overfull \\([hv])box \(([0-9.]+)pt too (?:wide|high)\)(.*)")
UNDERFULL = re.compile(r"^Underfull \\([hv])box \(badness ([0-9.]+)\)(.*)")
PAGINA_IMPRESSA = re.compile(r"\[[0-9]+[{\]]")


def _limite_de_estouro(eixo: str, opcoes) -> float:
    return opcoes.overfull_max_pt if eixo == "h" else opcoes.overfull_vbox_max_pt


def _limite_de_folga(eixo: str, opcoes) -> int:
    return opcoes.underfull_badness_max if eixo == "h" else opcoes.underfull_vbox_badness_max


def _numero(texto: str) -> float:
    try:
        return float(texto)
    except ValueError:
        return float("inf")


def validar_compilacao(entrada: EntradaDeLayout, config: ConfiguracaoValidador) -> list[Violacao]:
    if entrada.log is None:
        return []
    if entrada.log.problema:
        return [
            violacao(
                config,
                Regra.COMPILACAO,
                entrada.log.problema,
                "",
                "compile de novo e entregue o log completo da compilacao",
            )
        ]
    opcoes = config.layout.log
    linhas = entrada.log.linhas
    achados = []
    for posicao, linha in enumerate(linhas):
        if not linha.startswith(ERRO):
            continue
        contexto = linhas[posicao : posicao + opcoes.linhas_do_erro]
        trecho = " ".join(outra.strip() for outra in contexto)
        achados.append(
            violacao(
                config,
                Regra.COMPILACAO,
                recorte(f"pdflatex falhou: {linha[len(ERRO) :].strip()}", config),
                trecho,
                "corrija o comando ou o texto que o pdflatex recusou",
            )
        )
    return list(dict.fromkeys(achados))[: opcoes.erros_max]


def _contexto_da_caixa(linhas: tuple[str, ...], posicao: int, total: int) -> str:
    seguintes = []
    for linha in linhas[posicao + 1 : posicao + 1 + total]:
        if not linha.strip():
            break
        seguintes.append(linha.strip())
    return " ".join(seguintes)


def validar_caixas(entrada: EntradaDeLayout, config: ConfiguracaoValidador) -> list[Violacao]:
    if entrada.log is None or entrada.log.problema:
        return []
    opcoes = config.layout.log
    linhas = entrada.log.linhas
    achados = []
    paginas_impressas = 0
    for posicao, linha in enumerate(linhas):
        paginas_impressas += bool(PAGINA_IMPRESSA.search(linha))
        estouro = OVERFULL.match(linha)
        folga = UNDERFULL.match(linha)
        if estouro and _numero(estouro[2]) > _limite_de_estouro(estouro[1], opcoes):
            limite = _limite_de_estouro(estouro[1], opcoes)
            medida = f"{estouro[2]}pt a mais, limite {limite}pt"
            origem, tipo, eixo = estouro[3], "Overfull", estouro[1]
        elif folga and _numero(folga[2]) > _limite_de_folga(folga[1], opcoes):
            medida = f"badness {folga[2]}, limite {_limite_de_folga(folga[1], opcoes)}"
            origem, tipo, eixo = folga[3], "Underfull", folga[1]
        else:
            continue
        achados.append(
            violacao(
                config,
                Regra.CAIXA_ESTOURADA,
                recorte(
                    f"pagina {paginas_impressas + 1}, {tipo} {eixo}box, {medida}{origem}", config
                ),
                _contexto_da_caixa(linhas, posicao, opcoes.linhas_da_caixa),
                "encurte ou reescreva o trecho da linha que nao cabe",
            )
        )
    return list(dict.fromkeys(achados))[: opcoes.caixas_max]
