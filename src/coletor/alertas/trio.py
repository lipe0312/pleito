from __future__ import annotations

from src.coletor.alertas.cartao import (
    Acumulador,
    ResultadoCartoes,
    achado_de_vaga,
    campo_ou_vazio,
    linhas_do_corpo,
)
from src.coletor.alertas_config import PlataformaAlertas


def _campos_do_cartao(entre: list[str], plataforma: PlataformaAlertas) -> dict:
    nomes = plataforma.cartao_campos
    if len(entre) >= len(nomes):
        linhas = entre[-len(nomes) :]
    else:
        linhas = entre + [""] * (len(nomes) - len(entre))
    return {
        nome: campo_ou_vazio(linha, plataforma) for nome, linha in zip(nomes, linhas, strict=True)
    }


def extrair(corpo: str, plataforma: PlataformaAlertas, corpo_max_chars: int) -> ResultadoCartoes:
    linhas = linhas_do_corpo(corpo, corpo_max_chars)
    acumulador = Acumulador(plataforma)
    inicio = 0
    for posicao, linha in enumerate(linhas):
        achado = achado_de_vaga(linha, plataforma)
        if achado:
            acumulador.adicionar(achado, _campos_do_cartao(linhas[inicio:posicao], plataforma))
            inicio = posicao + 1
    return acumulador.resultado()
