from __future__ import annotations

import re

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.layout_entrada import EntradaDeLayout
from src.validador.resultado import Regra, Violacao
from src.validador.texto import violacao

CLASSE = re.compile(r"\\documentclass\s*\[([^\]]*)\]")
TAMANHO = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)pt\s*$")
ESPACAMENTO = re.compile(r"\\linespread\s*\{([^{}]*)\}")
GEOMETRIA = re.compile(r"\\usepackage\s*\[([^\]]*)\]\s*\{geometry\}")
MEDIDA = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-z]+)\s*$")


def _recusa(config: ConfiguracaoValidador, detalhe: str, trecho: str, sugestao: str) -> Violacao:
    return violacao(config, Regra.LIMITES_DE_LAYOUT, detalhe, trecho, sugestao)


def _fontes(preambulo: str, config: ConfiguracaoValidador) -> list[tuple[float, str]]:
    achados = []
    for classe in CLASSE.finditer(preambulo):
        tamanhos = [m[1] for o in classe[1].split(",") if (m := TAMANHO.match(o))]
        achados += [(float(t), classe[0]) for t in tamanhos]
        if not tamanhos:
            achados.append((config.layout.fonte_padrao_pt, classe[0]))
    return achados


def validar_limites(entrada: EntradaDeLayout, config: ConfiguracaoValidador) -> list[Violacao]:
    idioma = entrada.analise.contexto.idioma
    limites = config.layout.por_idioma[idioma]
    preambulo = entrada.analise.documento.preambulo
    achados: list[Violacao] = []
    for tamanho, trecho in _fontes(preambulo, config):
        if tamanho < limites.fonte_min_pt:
            achados.append(
                _recusa(
                    config,
                    f"fonte de {tamanho}pt abaixo do minimo de {limites.fonte_min_pt}pt ({idioma})",
                    trecho,
                    f"use fonte de pelo menos {limites.fonte_min_pt}pt",
                )
            )
    for achado in ESPACAMENTO.finditer(preambulo):
        try:
            valor = float(achado[1])
        except ValueError:
            achados.append(
                _recusa(config, "linespread ilegivel", achado[0], "use um numero em linespread")
            )
            continue
        if valor < limites.linespread_min:
            achados.append(
                _recusa(
                    config,
                    f"linespread {achado[1]} abaixo do minimo de {limites.linespread_min}"
                    f" ({idioma})",
                    achado[0],
                    f"use linespread de pelo menos {limites.linespread_min}",
                )
            )
    unidades = config.latex.medidas.unidades_mm
    for pacote in GEOMETRIA.finditer(preambulo):
        for opcao in pacote[1].split(","):
            chave, _, valor = opcao.partition("=")
            if chave.strip() not in config.layout.chaves_de_margem:
                continue
            medida = MEDIDA.match(valor)
            if medida is None or medida[2] not in unidades:
                achados.append(
                    _recusa(
                        config,
                        f"margem {chave.strip()} com medida ilegivel",
                        opcao.strip(),
                        "use um numero com unidade conhecida na margem",
                    )
                )
            elif float(medida[1]) * unidades[medida[2]] < limites.margem_min_mm:
                achados.append(
                    _recusa(
                        config,
                        f"margem {chave.strip()} abaixo do minimo de {limites.margem_min_mm}mm"
                        f" ({idioma})",
                        opcao.strip(),
                        f"use margem de pelo menos {limites.margem_min_mm}mm",
                    )
                )
    return list(dict.fromkeys(achados))
