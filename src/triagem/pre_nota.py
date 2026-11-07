from __future__ import annotations

import re
from datetime import date

from src.conteudo.modelo import Inventario
from src.triagem.configuracao import ConfiguracaoTriagem
from src.triagem.contratos import VagaTriagem

NOTA_MAXIMA = 100


def _aparece(termo: str, texto: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(termo)}(?!\w)", texto, re.IGNORECASE) is not None


def _fracao_stack(texto: str, inventario: Inventario, config: ConfiguracaoTriagem) -> float:
    regras = config.pre_nota
    techs = {item.tech for item in inventario.techs}
    cobertas = {tech for tech in techs if _aparece(tech, texto)}
    equivalentes = {
        equivalencia.pedido
        for equivalencia in inventario.equivalencias
        if equivalencia.tem in techs
        and equivalencia.pedido not in techs
        and _aparece(equivalencia.pedido, texto)
    }
    conhecidas = {tech for tech in regras.techs_fora_do_inventario if _aparece(tech, texto)}
    ausentes = conhecidas - equivalentes - techs
    total = len(cobertas) + len(equivalentes) + len(ausentes)
    if total == 0:
        return 0.0
    valor = len(cobertas) + regras.equivalente_peso * len(equivalentes)
    return (valor / total) * min(1.0, valor / regras.techs_para_nota_cheia)


def _fracao_pais(vaga: VagaTriagem, config: ConfiguracaoTriagem) -> float:
    if not vaga.pais:
        return config.pre_nota.pais_ausente
    return config.pre_nota.pais.get(vaga.pais, config.pre_nota.pais_outro)


def _fracao_recencia(vaga: VagaTriagem, config: ConfiguracaoTriagem, hoje: date) -> float:
    if vaga.publicada_em is None:
        return config.pre_nota.recencia_sem_data
    dias = max((hoje - vaga.publicada_em).days, 0)
    return max(0.0, 1 - dias / config.filtros.eliminatorios.idade_maxima_dias)


def calcular_pre_nota(
    vaga: VagaTriagem, inventario: Inventario, config: ConfiguracaoTriagem, hoje: date
) -> int:
    pesos = config.filtros.pontuacao
    texto = f"{vaga.titulo}\n{vaga.descricao[: config.descricao_max_chars]}"
    parcelas = (
        (pesos.peso_stack, _fracao_stack(texto, inventario, config)),
        (pesos.peso_senioridade, config.pre_nota.senioridade.get(vaga.senioridade, 0.0)),
        (pesos.peso_modelo, config.pre_nota.modelo.get(vaga.modelo, 0.0)),
        (pesos.peso_pais, _fracao_pais(vaga, config)),
        (pesos.peso_empresa_alvo, 1.0 if vaga.alvo else 0.0),
        (pesos.peso_recencia, _fracao_recencia(vaga, config, hoje)),
    )
    total_pesos = sum(peso for peso, _ in parcelas)
    pontos = sum(peso * fracao for peso, fracao in parcelas)
    return round(NOTA_MAXIMA * pontos / total_pesos)
