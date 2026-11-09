from __future__ import annotations

from src.coletor.alertas.cartao import (
    Acumulador,
    ResultadoCartoes,
    achado_de_vaga,
    campo_ou_vazio,
    linhas_do_corpo,
)
from src.coletor.alertas_config import PlataformaAlertas


def _campos_antes_do_link(linhas: list[str], posicao: int, plataforma: PlataformaAlertas) -> dict:
    nomes = plataforma.cartao_campos
    anteriores = linhas[max(0, posicao - len(nomes)) : posicao]
    anteriores = [""] * (len(nomes) - len(anteriores)) + anteriores
    return {
        nome: campo_ou_vazio(linha, plataforma)
        for nome, linha in zip(nomes, anteriores, strict=True)
    }


def extrair(corpo: str, plataforma: PlataformaAlertas, corpo_max_chars: int) -> ResultadoCartoes:
    linhas = linhas_do_corpo(corpo, corpo_max_chars)
    acumulador = Acumulador(plataforma)
    for posicao, linha in enumerate(linhas):
        achado = achado_de_vaga(linha, plataforma)
        if achado:
            acumulador.adicionar(achado, _campos_antes_do_link(linhas, posicao, plataforma))
    return acumulador.resultado()
