from __future__ import annotations

from src.db.conexao import conectar
from src.validador.analise import Vaga

SQL_VAGA = """
SELECT v.titulo, v.descricao, coalesce(e.nome, '')
FROM pleito.vaga v
LEFT JOIN pleito.empresa e ON e.id = v.empresa_id
WHERE v.id = %s
"""

SQL_PENDENCIA = """
INSERT INTO pleito.pendencia (vaga_id, categoria, detalhe, link)
VALUES (%s, %s, %s, %s)
"""


class VagaInexistente(LookupError):
    pass


def carregar_vaga(vaga_id: int) -> Vaga:
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute(SQL_VAGA, (vaga_id,))
        linha = cursor.fetchone()
    if linha is None:
        raise VagaInexistente(f"vaga {vaga_id} nao existe")
    titulo, descricao, empresa = linha
    return Vaga(empresa=empresa, descricao=descricao, titulo=titulo)


def inserir_pendencia(vaga_id: int, categoria: str, detalhe: str, link: str) -> None:
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute(SQL_PENDENCIA, (vaga_id, categoria, detalhe, link or None))
