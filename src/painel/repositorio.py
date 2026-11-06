from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Protocol

import yaml

from src.config import carregar
from src.db.conexao import conectar

COMPONENTE = "painel"

SQL_EVENTOS_DO_DIA = """
SELECT ev.id, v.titulo, e.nome, ev.tipo, ev.remetente, ev.autenticado, ev.fila, ev.recebido_em
FROM pleito.evento_email ev
LEFT JOIN pleito.vaga v ON v.id = ev.vaga_id
LEFT JOIN pleito.empresa e ON e.id = v.empresa_id
WHERE ev.recebido_em >= %s AND ev.recebido_em < %s
ORDER BY ev.recebido_em DESC, ev.id DESC
LIMIT %s
"""
SQL_PENDENCIAS_ABERTAS = """
SELECT p.id, p.categoria, p.detalhe, v.titulo, e.nome, p.criada_em
FROM pleito.pendencia p
JOIN pleito.vaga v ON v.id = p.vaga_id
LEFT JOIN pleito.empresa e ON e.id = v.empresa_id
WHERE p.resolvida_em IS NULL
ORDER BY p.criada_em ASC, p.id ASC
LIMIT %s
"""
SQL_CANDIDATURAS = """
SELECT v.id, v.titulo, e.nome, v.estado::text, u.tipo, u.remetente, u.recebido_em
FROM pleito.vaga v
LEFT JOIN pleito.empresa e ON e.id = v.empresa_id
LEFT JOIN LATERAL (
    SELECT ev.tipo, ev.remetente, ev.recebido_em
    FROM pleito.evento_email ev
    WHERE ev.vaga_id = v.id
    ORDER BY ev.recebido_em DESC, ev.id DESC
    LIMIT 1
) u ON true
WHERE v.estado::text = ANY(%s)
ORDER BY u.recebido_em DESC NULLS LAST, v.id DESC
LIMIT %s
"""


@dataclass(frozen=True, slots=True)
class EventoDoDia:
    id: int
    vaga: str | None
    empresa: str | None
    tipo: str
    remetente: str
    autenticado: bool
    fila: str | None
    recebido_em: datetime


@dataclass(frozen=True, slots=True)
class PendenciaAberta:
    id: int
    categoria: str
    detalhe: str
    vaga: str
    empresa: str | None
    criada_em: datetime


@dataclass(frozen=True, slots=True)
class UltimoEvento:
    tipo: str
    remetente: str
    recebido_em: datetime


@dataclass(frozen=True, slots=True)
class Candidatura:
    id: int
    titulo: str
    empresa: str | None
    estado: str
    ultimo_evento: UltimoEvento | None


class RepositorioLeitura(Protocol):
    def eventos_do_dia(self, inicio: datetime, fim: datetime) -> list[EventoDoDia]: ...

    def pendencias_abertas(self) -> list[PendenciaAberta]: ...

    def candidaturas(self, estados: Sequence[str]) -> list[Candidatura]: ...


class RepositorioBanco:
    def _consultar(self, sql: str, parametros: tuple) -> list[tuple]:
        with conectar(COMPONENTE) as conexao:
            conexao.read_only = True
            with conexao.cursor() as cursor:
                cursor.execute(sql, parametros)
                return cursor.fetchall()

    def eventos_do_dia(self, inicio: datetime, fim: datetime) -> list[EventoDoDia]:
        limite = carregar("painel")["limite_eventos_dia"]
        linhas = self._consultar(SQL_EVENTOS_DO_DIA, (inicio, fim, limite))
        return [EventoDoDia(*linha) for linha in linhas]

    def pendencias_abertas(self) -> list[PendenciaAberta]:
        limite = carregar("painel")["limite_pendencias"]
        linhas = self._consultar(SQL_PENDENCIAS_ABERTAS, (limite,))
        return [PendenciaAberta(*linha) for linha in linhas]

    def candidaturas(self, estados: Sequence[str]) -> list[Candidatura]:
        limite = carregar("painel")["limite_candidaturas"]
        linhas = self._consultar(SQL_CANDIDATURAS, (list(estados), limite))
        return [
            Candidatura(
                id=id_vaga,
                titulo=titulo,
                empresa=empresa,
                estado=estado,
                ultimo_evento=UltimoEvento(tipo, remetente, recebido_em) if tipo else None,
            )
            for id_vaga, titulo, empresa, estado, tipo, remetente, recebido_em in linhas
        ]


def _momento(agora: datetime, dias_atras: int, hora: str) -> datetime:
    dia: date = agora.date() - timedelta(days=dias_atras)
    return datetime.combine(dia, time.fromisoformat(hora), tzinfo=agora.tzinfo)


class RepositorioFicticio:
    def __init__(
        self,
        eventos: list[EventoDoDia],
        pendencias: list[PendenciaAberta],
        candidaturas: list[Candidatura],
    ) -> None:
        self._eventos = eventos
        self._pendencias = pendencias
        self._candidaturas = candidaturas

    @classmethod
    def de_dados(cls, dados: dict, agora: datetime) -> RepositorioFicticio:
        eventos = [
            EventoDoDia(
                id=bruto["id"],
                vaga=bruto["vaga"],
                empresa=bruto["empresa"],
                tipo=bruto["tipo"],
                remetente=bruto["remetente"],
                autenticado=bruto["autenticado"],
                fila=bruto["fila"],
                recebido_em=_momento(agora, bruto.get("dias_atras", 0), bruto["hora"]),
            )
            for bruto in dados.get("eventos", [])
        ]
        pendencias = [
            PendenciaAberta(
                id=bruto["id"],
                categoria=bruto["categoria"],
                detalhe=bruto["detalhe"],
                vaga=bruto["vaga"],
                empresa=bruto["empresa"],
                criada_em=_momento(agora, bruto.get("dias_atras", 0), bruto.get("hora", "00:00")),
            )
            for bruto in dados.get("pendencias", [])
        ]
        candidaturas = [
            Candidatura(
                id=bruto["id"],
                titulo=bruto["titulo"],
                empresa=bruto["empresa"],
                estado=bruto["estado"],
                ultimo_evento=_ultimo_evento(bruto["ultimo_evento"], agora),
            )
            for bruto in dados.get("candidaturas", [])
        ]
        return cls(eventos, pendencias, candidaturas)

    @classmethod
    def de_arquivo(cls, caminho: Path, agora: datetime) -> RepositorioFicticio:
        with Path(caminho).open(encoding="utf-8") as arquivo:
            return cls.de_dados(yaml.safe_load(arquivo) or {}, agora)

    def eventos_do_dia(self, inicio: datetime, fim: datetime) -> list[EventoDoDia]:
        do_dia = [e for e in self._eventos if inicio <= e.recebido_em < fim]
        return sorted(do_dia, key=lambda e: (e.recebido_em, e.id), reverse=True)

    def pendencias_abertas(self) -> list[PendenciaAberta]:
        return sorted(self._pendencias, key=lambda p: (p.criada_em, p.id))

    def candidaturas(self, estados: Sequence[str]) -> list[Candidatura]:
        escolhidas = [c for c in self._candidaturas if c.estado in estados]
        return sorted(escolhidas, key=_chave_recente, reverse=True)


def _chave_recente(candidatura: Candidatura) -> tuple[bool, float]:
    ultimo = candidatura.ultimo_evento
    return (ultimo is not None, ultimo.recebido_em.timestamp() if ultimo else 0.0)


def _ultimo_evento(bruto: dict | None, agora: datetime) -> UltimoEvento | None:
    if bruto is None:
        return None
    return UltimoEvento(
        tipo=bruto["tipo"],
        remetente=bruto["remetente"],
        recebido_em=_momento(agora, bruto.get("dias_atras", 0), bruto["hora"]),
    )
