from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from src.config import carregar
from src.email.modelo import Etapa


def normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


@dataclass(frozen=True, slots=True)
class Plataforma:
    nome: str
    marcas: tuple[str, ...]
    dominios: tuple[str, ...]
    caixas: tuple[str, ...]
    gatilho_candidatura: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PadroesEtapa:
    assunto: tuple[str, ...]
    corpo: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Regras:
    limiar_confianca: float
    margem_ambiguidade: float
    corpo_max_chars: int
    peso_assunto: float
    peso_corpo: float
    confianca_suspeito: float
    confianca_remetente_desconhecido_max: float
    autenticacao_aprovada: tuple[str, ...]
    plataforma_alertas: str
    plataformas: dict[str, Plataforma]
    etapas: dict[Etapa, PadroesEtapa]


def _normalizados(valores: list[str]) -> tuple[str, ...]:
    return tuple(normalizar(valor) for valor in valores)


def montar(bruto: dict) -> Regras:
    plataformas = {
        nome: Plataforma(
            nome=nome,
            marcas=_normalizados(dados["marcas"]),
            dominios=tuple(dominio.lower() for dominio in dados["dominios"]),
            caixas=tuple(caixa.lower() for caixa in dados["caixas"]),
            gatilho_candidatura=_normalizados(dados["gatilho_candidatura"]),
        )
        for nome, dados in bruto["plataformas"].items()
    }
    etapas = {
        Etapa(nome): PadroesEtapa(
            assunto=_normalizados(dados["assunto"]), corpo=_normalizados(dados["corpo"])
        )
        for nome, dados in bruto["etapas"].items()
    }
    return Regras(
        limiar_confianca=float(bruto["limiar_confianca"]),
        margem_ambiguidade=float(bruto["margem_ambiguidade"]),
        corpo_max_chars=int(bruto["corpo_max_chars"]),
        peso_assunto=float(bruto["peso"]["assunto"]),
        peso_corpo=float(bruto["peso"]["corpo"]),
        confianca_suspeito=float(bruto["confianca"]["suspeito"]),
        confianca_remetente_desconhecido_max=float(
            bruto["confianca"]["remetente_desconhecido_max"]
        ),
        autenticacao_aprovada=tuple(
            normalizar(termo).replace(" ", "") for termo in bruto["autenticacao_aprovada"]
        ),
        plataforma_alertas=bruto["plataforma_alertas"],
        plataformas=plataformas,
        etapas=etapas,
    )


@lru_cache(maxsize=1)
def regras() -> Regras:
    return montar(carregar("emails"))
