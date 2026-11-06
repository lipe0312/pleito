from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from src.config import carregar
from src.email.modelo import Classificacao, Email, Etapa
from src.email.regras import Regras, normalizar, regras
from src.email.remetente import autenticacao_aprovada, dominio_de

SQL_POR_DOMINIO = """
SELECT v.id
FROM vaga v
JOIN empresa e ON e.id = v.empresa_id
WHERE lower(e.dominio) = %s AND v.estado::text = ANY(%s)
ORDER BY v.id
LIMIT %s
"""
SQL_POR_PLATAFORMA = """
SELECT v.id, e.nome_norm
FROM vaga v
JOIN candidatura c ON c.vaga_id = v.id
JOIN empresa e ON e.id = v.empresa_id
WHERE c.plataforma = %s AND v.estado::text = ANY(%s)
ORDER BY v.id
LIMIT %s
"""


@dataclass(frozen=True, slots=True)
class RegraVinculo:
    estados_candidatos: tuple[str, ...]
    dominios_ignorados: frozenset[str]
    limite_candidatas: int


def montar_regra_vinculo(bruto: dict) -> RegraVinculo:
    return RegraVinculo(
        estados_candidatos=tuple(bruto["estados_candidatos"]),
        dominios_ignorados=frozenset(dominio.lower() for dominio in bruto["dominios_ignorados"]),
        limite_candidatas=int(bruto["limite_candidatas"]),
    )


@lru_cache(maxsize=1)
def regra_de_vinculo() -> RegraVinculo:
    return montar_regra_vinculo(carregar("eventos_email")["vinculo"])


def _unica(candidatas: list) -> int | None:
    return candidatas[0] if len(candidatas) == 1 else None


def _dominio_de_plataforma(dominio: str, configuradas: Regras) -> bool:
    return any(dominio in p.dominios for p in configuradas.plataformas.values())


def _por_dominio(cursor, email: Email, regra: RegraVinculo, configuradas: Regras) -> int | None:
    dominio = dominio_de(email.remetente)
    if (
        not dominio
        or not dominio.isascii()
        or dominio in regra.dominios_ignorados
        or _dominio_de_plataforma(dominio, configuradas)
    ):
        return None
    if email.reply_to and dominio_de(email.reply_to) != dominio:
        return None
    cursor.execute(
        SQL_POR_DOMINIO,
        (dominio, list(regra.estados_candidatos), regra.limite_candidatas),
    )
    return _unica([linha[0] for linha in cursor.fetchall()])


def _cita(texto: str, nome: str) -> bool:
    return bool(nome) and re.search(rf"(?<!\w){re.escape(nome)}(?!\w)", texto) is not None


def _por_plataforma(
    cursor, email: Email, plataforma: str, regra: RegraVinculo, configuradas: Regras
) -> int | None:
    cursor.execute(
        SQL_POR_PLATAFORMA,
        (plataforma, list(regra.estados_candidatos), regra.limite_candidatas),
    )
    texto = normalizar(f"{email.assunto} {(email.corpo or '')[: configuradas.corpo_max_chars]}")
    citadas = [vaga_id for vaga_id, nome in cursor.fetchall() if _cita(texto, normalizar(nome))]
    return _unica(citadas)


def vaga_do_email(
    cursor,
    email: Email,
    classificacao: Classificacao,
    regra: RegraVinculo | None = None,
    configuradas: Regras | None = None,
) -> int | None:
    regra = regra or regra_de_vinculo()
    configuradas = configuradas or regras()
    if classificacao.etapa is Etapa.SUSPEITO or not autenticacao_aprovada(
        email.autenticacao, configuradas
    ):
        return None
    vaga_id = _por_dominio(cursor, email, regra, configuradas)
    if vaga_id is not None:
        return vaga_id
    plataforma = classificacao.plataforma
    if plataforma is None or plataforma == configuradas.plataforma_alertas:
        return None
    return _por_plataforma(cursor, email, plataforma, regra, configuradas)
