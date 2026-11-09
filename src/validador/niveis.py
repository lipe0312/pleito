from __future__ import annotations

from dataclasses import replace

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.resultado import GRAVIDADE, REGRAS_DE_SEGURANCA, Nivel, Violacao

EVIDENCIA_REGRA_EM_OK = "regra em ok na configuracao"


def aplicar_niveis(
    violacoes: list[Violacao] | tuple[Violacao, ...], config: ConfiguracaoValidador
) -> list[Violacao]:
    saida = []
    for achado in violacoes:
        if achado.regra in REGRAS_DE_SEGURANCA:
            saida.append(replace(achado, nivel=Nivel.BLOQUEIA))
            continue
        teto = config.niveis[achado.regra]
        nivel = min(achado.nivel, teto, key=GRAVIDADE.__getitem__)
        evidencia = achado.evidencia
        if nivel is Nivel.OK and achado.nivel is not Nivel.OK and not evidencia:
            evidencia = EVIDENCIA_REGRA_EM_OK
        saida.append(replace(achado, nivel=nivel, evidencia=evidencia))
    return saida
