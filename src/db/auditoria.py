from __future__ import annotations

from collections.abc import Mapping

from psycopg import Connection
from psycopg.types.json import Jsonb


def registrar_auditoria(
    conexao: Connection,
    ator: str,
    acao: str,
    entidade: str,
    entidade_id: str | None = None,
    antes: Mapping[str, object] | None = None,
    depois: Mapping[str, object] | None = None,
) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO auditoria (ator, acao, entidade, entidade_id, antes, depois)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                ator,
                acao,
                entidade,
                entidade_id,
                Jsonb(dict(antes)) if antes is not None else None,
                Jsonb(dict(depois)) if depois is not None else None,
            ),
        )
