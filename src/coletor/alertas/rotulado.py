from __future__ import annotations

from src.coletor.alertas.cartao import (
    Acumulador,
    ResultadoCartoes,
    achado_de_vaga,
    campo_ou_vazio,
    limpar,
    linhas_do_corpo,
)
from src.coletor.alertas_config import PlataformaAlertas
from src.email.regras import normalizar


def _campo_da_linha(linha: str, plataforma: PlataformaAlertas) -> tuple[str, str] | None:
    normalizada = normalizar(linha)
    for campo in plataforma.cartao_campos:
        for rotulo in plataforma.rotulos_campos[campo]:
            if normalizada.startswith(f"{rotulo}:"):
                valor = limpar(linha.partition(":")[2])
                return campo, campo_ou_vazio(valor, plataforma)
    return None


def extrair(corpo: str, plataforma: PlataformaAlertas, corpo_max_chars: int) -> ResultadoCartoes:
    acumulador = Acumulador(plataforma)
    campos: dict[str, str] = {}
    for linha in linhas_do_corpo(corpo, corpo_max_chars):
        if linha.startswith(plataforma.separador_cartao):
            campos = {}
            continue
        achado = achado_de_vaga(linha, plataforma)
        if achado:
            acumulador.adicionar(achado, campos)
            campos = {}
            continue
        encontrado = _campo_da_linha(linha, plataforma)
        if encontrado:
            campos.setdefault(*encontrado)
    return acumulador.resultado()
