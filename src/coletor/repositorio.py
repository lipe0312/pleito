from __future__ import annotations

from dataclasses import dataclass

from src.coletor.contratos import VagaBruta

SQL_FONTE = "SELECT id FROM fonte WHERE slug = %s"
SQL_EMPRESA_CRIAR = (
    "INSERT INTO empresa (nome) VALUES (%s) ON CONFLICT ON CONSTRAINT empresa_nome_unica DO NOTHING"
)
SQL_EMPRESA = "SELECT id FROM empresa WHERE nome_norm = lower(btrim(%s))"
SQL_VAGA = """
INSERT INTO vaga (
    fonte_id, empresa_id, id_externo, url, titulo, descricao, local, pais,
    senioridade, modelo, publicada_em, hash_conteudo
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::senioridade, %s::modelo_trabalho, %s, %s)
ON CONFLICT DO NOTHING
RETURNING id
"""


class FonteDesconhecida(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResumoGravacao:
    recebidas: int
    inseridas: int
    duplicadas: int


def chave_deduplicacao(vaga: VagaBruta) -> tuple[str, str, str]:
    return (vaga.fonte, vaga.empresa.strip().lower(), vaga.hash_conteudo)


def deduplicar_lote(vagas: list[VagaBruta]) -> list[VagaBruta]:
    vistas: set[tuple[str, str, str]] = set()
    unicas = []
    for vaga in vagas:
        chave = chave_deduplicacao(vaga)
        if chave not in vistas:
            vistas.add(chave)
            unicas.append(vaga)
    return unicas


def _texto(valor: str) -> str:
    return valor.replace("\x00", "")


def _id_fonte(cursor, slug: str, cache: dict[str, int]) -> int:
    if slug not in cache:
        cursor.execute(SQL_FONTE, (slug,))
        linha = cursor.fetchone()
        if linha is None:
            raise FonteDesconhecida(f"fonte sem linha no banco: {slug}")
        cache[slug] = linha[0]
    return cache[slug]


def _id_empresa(cursor, nome: str, cache: dict[str, int | None]) -> int | None:
    limpo = _texto(nome).strip()
    if not limpo:
        return None
    chave = limpo.lower()
    if chave not in cache:
        cursor.execute(SQL_EMPRESA_CRIAR, (limpo,))
        cursor.execute(SQL_EMPRESA, (limpo,))
        linha = cursor.fetchone()
        cache[chave] = linha[0] if linha else None
    return cache[chave]


def gravar_vagas(conexao, vagas: list[VagaBruta]) -> ResumoGravacao:
    unicas = deduplicar_lote(vagas)
    inseridas = 0
    fontes: dict[str, int] = {}
    empresas: dict[str, int | None] = {}
    with conexao.cursor() as cursor:
        for vaga in unicas:
            fonte_id = _id_fonte(cursor, vaga.fonte, fontes)
            empresa_id = _id_empresa(cursor, vaga.empresa, empresas)
            cursor.execute(
                SQL_VAGA,
                (
                    fonte_id,
                    empresa_id,
                    _texto(vaga.id_externo),
                    _texto(vaga.url),
                    _texto(vaga.titulo),
                    _texto(vaga.descricao),
                    _texto(vaga.local) or None,
                    vaga.pais or None,
                    vaga.senioridade.value,
                    vaga.modelo.value,
                    vaga.publicada_em,
                    bytes.fromhex(vaga.hash_conteudo),
                ),
            )
            if cursor.fetchone() is not None:
                inseridas += 1
    return ResumoGravacao(
        recebidas=len(vagas), inseridas=inseridas, duplicadas=len(vagas) - inseridas
    )
