from __future__ import annotations

from collections.abc import Callable
from datetime import date

from src.coletor.alertas import rotulado, trio
from src.coletor.alertas.cartao import ResultadoCartoes, vaga_do_cartao
from src.coletor.alertas_config import PlataformaAlertas, configuracao_alertas
from src.coletor.contratos import VagaBruta

Extrator = Callable[[str, PlataformaAlertas, int], ResultadoCartoes]

EXTRATORES: dict[str, Extrator] = {
    "trio_antes_do_link": trio.extrair,
    "bloco_rotulado": rotulado.extrair,
}


class FormatoDesconhecido(ValueError):
    pass


def extrator_da(plataforma: PlataformaAlertas) -> Extrator:
    try:
        return EXTRATORES[plataforma.formato]
    except KeyError:
        raise FormatoDesconhecido(f"{plataforma.nome}: formato {plataforma.formato}") from None


def extrair_cartoes_do_formato(
    corpo: str, plataforma: PlataformaAlertas, corpo_max_chars: int
) -> ResultadoCartoes:
    return extrator_da(plataforma)(corpo, plataforma, corpo_max_chars)


def extrair_vagas(
    corpo: str,
    plataforma: PlataformaAlertas,
    recebido_em: date | None,
    corpo_max_chars: int | None = None,
) -> list[VagaBruta]:
    limite = corpo_max_chars or configuracao_alertas().corpo_max_chars
    achados = extrair_cartoes_do_formato(corpo, plataforma, limite)
    return [vaga_do_cartao(cartao, plataforma, recebido_em) for cartao in achados.completos]
