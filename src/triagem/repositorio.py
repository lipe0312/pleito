from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.coletor.contratos import ModeloTrabalho, Senioridade
from src.db.auditoria import registrar_auditoria
from src.triagem.contratos import SEPARADOR_DETALHE, VagaAguardando, VagaTriagem

ATOR = "triagem"
ACAO_PONTUACAO = "pontuacao_final"
ENTIDADE = "vaga"

COLUNAS = """
    v.id, f.slug, COALESCE(e.nome, ''), COALESCE(e.alvo, false), v.titulo, v.url, v.descricao,
    COALESCE(v.local, ''), COALESCE(v.pais, ''), v.senioridade::text, v.modelo::text,
    v.publicada_em
"""
ORIGEM = """
FROM vaga v
JOIN fonte f ON f.id = v.fonte_id
LEFT JOIN empresa e ON e.id = v.empresa_id
"""
SQL_PENDENTES = f"""
SELECT {COLUNAS} {ORIGEM}
WHERE v.estado = 'descoberta' AND v.motivo_descarte IS NULL
  AND (%(ids)s::bigint[] IS NULL OR v.id = ANY(%(ids)s))
ORDER BY v.id
"""
SQL_VISTAS = f"""
SELECT {COLUNAS} {ORIGEM}
WHERE NOT (v.estado = 'descoberta' AND v.motivo_descarte IS NULL)
ORDER BY v.id
"""
SQL_AGUARDANDO = f"""
SELECT {COLUNAS}, v.nota {ORIGEM}
WHERE v.estado = 'triada' AND v.motivo_descarte IS NULL
  AND (%(ids)s::bigint[] IS NULL OR v.id = ANY(%(ids)s))
ORDER BY v.id
"""
SQL_DESCARTAR = """
UPDATE vaga SET motivo_descarte = %s, nota = %s
WHERE id = %s AND estado IN ('descoberta', 'triada') AND motivo_descarte IS NULL
"""
SQL_TRIAR = """
UPDATE vaga SET estado = 'triada', nota = %s
WHERE id = %s AND estado = 'descoberta' AND motivo_descarte IS NULL
"""
SQL_PONTUAR = """
UPDATE vaga SET estado = 'pontuada', nota = %s
WHERE id = %s AND estado = 'triada' AND motivo_descarte IS NULL
"""
SQL_CACHE = """
SELECT depois -> 'resultado' FROM auditoria
WHERE entidade = %s AND acao = %s AND depois ->> 'hash_entrada' = %s
ORDER BY id DESC LIMIT 1
"""
SQL_DESCARTES = """
SELECT v.id, v.titulo, COALESCE(e.nome, ''), v.motivo_descarte, v.nota
FROM vaga v LEFT JOIN empresa e ON e.id = v.empresa_id
WHERE v.motivo_descarte IS NOT NULL
  AND (%(codigo)s::text IS NULL OR split_part(v.motivo_descarte, %(separador)s, 1) = %(codigo)s)
ORDER BY v.id DESC
LIMIT %(limite)s
"""
SQL_DESCARTES_POR_MOTIVO = """
SELECT split_part(motivo_descarte, %s, 1) AS codigo, count(*)
FROM vaga WHERE motivo_descarte IS NOT NULL
GROUP BY codigo ORDER BY count(*) DESC, codigo
"""


class TransicaoRecusada(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Descarte:
    vaga_id: int
    titulo: str
    empresa: str
    motivo: str
    nota: int | None


def _vaga(linha: tuple) -> VagaTriagem:
    return VagaTriagem(
        id=linha[0],
        fonte=linha[1],
        empresa=linha[2],
        alvo=linha[3],
        titulo=linha[4],
        url=linha[5],
        descricao=linha[6],
        local=linha[7],
        pais=linha[8],
        senioridade=Senioridade(linha[9]),
        modelo=ModeloTrabalho(linha[10]),
        publicada_em=linha[11],
    )


class RepositorioPostgres:
    def __init__(self, conexao, ids: Sequence[int] | None = None) -> None:
        self._conexao = conexao
        self._ids = list(ids) if ids is not None else None

    def _consultar(self, sql: str, parametros: dict | tuple = ()) -> list[tuple]:
        with self._conexao.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()

    def pendentes(self) -> list[VagaTriagem]:
        return [_vaga(linha) for linha in self._consultar(SQL_PENDENTES, {"ids": self._ids})]

    def vistas(self) -> list[VagaTriagem]:
        return [_vaga(linha) for linha in self._consultar(SQL_VISTAS)]

    def aguardando(self) -> list[VagaAguardando]:
        linhas = self._consultar(SQL_AGUARDANDO, {"ids": self._ids})
        return [VagaAguardando(_vaga(linha[:-1]), int(linha[-1])) for linha in linhas]

    def _atualizar(self, sql: str, parametros: tuple, acao: str) -> None:
        with self._conexao.cursor() as cursor:
            cursor.execute(sql, parametros)
            if cursor.rowcount != 1:
                raise TransicaoRecusada(f"vaga {parametros[-1]} nao pode {acao}")

    def descartar(self, vaga_id: int, motivo: str, nota: int | None = None) -> None:
        self._atualizar(SQL_DESCARTAR, (motivo, nota, vaga_id), "ser descartada")

    def triar(self, vaga_id: int, pre_nota: int) -> None:
        self._atualizar(SQL_TRIAR, (pre_nota, vaga_id), "ser triada")

    def pontuar(self, vaga_id: int, nota: int, registro: dict, origem: str) -> None:
        self._atualizar(SQL_PONTUAR, (nota, vaga_id), "ser pontuada")
        registrar_auditoria(
            self._conexao,
            ator=ATOR,
            acao=ACAO_PONTUACAO,
            entidade=ENTIDADE,
            entidade_id=str(vaga_id),
            depois={**registro, "origem": origem},
        )

    def resultado_em_cache(self, hash_entrada: str) -> dict | None:
        linhas = self._consultar(SQL_CACHE, (ENTIDADE, ACAO_PONTUACAO, hash_entrada))
        return linhas[0][0] if linhas else None

    def confirmar(self) -> None:
        self._conexao.commit()


def listar_descartes(conexao, codigo: str | None = None, limite: int = 100) -> list[Descarte]:
    with conexao.cursor() as cursor:
        cursor.execute(
            SQL_DESCARTES, {"codigo": codigo, "separador": SEPARADOR_DETALHE, "limite": limite}
        )
        return [
            Descarte(
                vaga_id=linha[0],
                titulo=linha[1],
                empresa=linha[2],
                motivo=linha[3],
                nota=None if linha[4] is None else int(linha[4]),
            )
            for linha in cursor.fetchall()
        ]


def contar_descartes_por_motivo(conexao) -> dict[str, int]:
    with conexao.cursor() as cursor:
        cursor.execute(SQL_DESCARTES_POR_MOTIVO, (SEPARADOR_DETALHE,))
        return {codigo: total for codigo, total in cursor.fetchall()}
