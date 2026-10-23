from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

from src.config import carregar
from src.email.modelo import Classificacao, Etapa
from src.email.regras import regras


class MotivoFila(StrEnum):
    SUSPEITO = "suspeito"
    NAO_RECONHECIDO = "nao_reconhecido"
    NAO_AUTENTICADO = "nao_autenticado"
    ABAIXO_DO_LIMIAR = "abaixo_do_limiar"
    SEM_VAGA = "sem_vaga"
    TRANSICAO_INVALIDA = "transicao_invalida"
    APLICADO = "aplicado"
    SEM_MUDANCA = "sem_mudanca"


@dataclass(frozen=True, slots=True)
class Politica:
    ator: str
    limiar: float
    estado_por_etapa: dict[Etapa, str]
    origens_permitidas: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class Decisao:
    fila: Etapa | None
    motivo: MotivoFila
    estado_novo: str | None = None


def _fila(etapa: Etapa, motivo: MotivoFila) -> Decisao:
    return Decisao(fila=etapa, motivo=motivo)


def decidir(
    classificacao: Classificacao,
    autenticado: bool,
    estado_atual: str | None,
    configurada: Politica,
) -> Decisao:
    if classificacao.etapa is Etapa.SUSPEITO:
        return _fila(Etapa.SUSPEITO, MotivoFila.SUSPEITO)
    destino = configurada.estado_por_etapa.get(classificacao.etapa)
    if destino is None:
        return _fila(Etapa.CLASSIFICAR, MotivoFila.NAO_RECONHECIDO)
    if not autenticado:
        return _fila(Etapa.CLASSIFICAR, MotivoFila.NAO_AUTENTICADO)
    if classificacao.confianca < configurada.limiar:
        return _fila(Etapa.CLASSIFICAR, MotivoFila.ABAIXO_DO_LIMIAR)
    if estado_atual is None:
        return _fila(Etapa.CLASSIFICAR, MotivoFila.SEM_VAGA)
    if estado_atual == destino:
        return Decisao(fila=None, motivo=MotivoFila.SEM_MUDANCA)
    if estado_atual not in configurada.origens_permitidas.get(destino, ()):
        return _fila(Etapa.CLASSIFICAR, MotivoFila.TRANSICAO_INVALIDA)
    return Decisao(fila=None, motivo=MotivoFila.APLICADO, estado_novo=destino)


def montar_politica(bruto: dict, limiar: float) -> Politica:
    return Politica(
        ator=bruto["ator"],
        limiar=limiar,
        estado_por_etapa={
            Etapa(etapa): estado for etapa, estado in bruto["estado_por_etapa"].items()
        },
        origens_permitidas={
            destino: tuple(origens) for destino, origens in bruto["origens_permitidas"].items()
        },
    )


@lru_cache(maxsize=1)
def politica() -> Politica:
    return montar_politica(carregar("eventos_email"), regras().limiar_confianca)
