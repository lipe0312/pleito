from __future__ import annotations

import uuid

import pytest

from src.coletor.contratos import VagaBruta
from src.coletor.repositorio import ResumoGravacao, gravar_vagas
from src.db.conexao import conectar

ATAQUE = "'; DROP TABLE vagas; --"


@pytest.fixture
def rotulo(banco):
    sufixo = uuid.uuid4().hex[:12]
    yield sufixo
    with banco.cursor() as cursor:
        cursor.execute("DELETE FROM pleito.vaga WHERE id_externo LIKE %s", (f"teste-{sufixo}%",))
        cursor.execute("DELETE FROM pleito.empresa WHERE nome_norm LIKE %s", (f"%{sufixo}%",))
    banco.commit()


def _vaga(rotulo: str, id_externo: str = "a", **campos) -> VagaBruta:
    base = {
        "fonte": "greenhouse",
        "id_externo": f"teste-{rotulo}-{id_externo}",
        "url": "https://boards.greenhouse.io/empresaficticia/jobs/1",
        "titulo": "Estagio em Dados",
        "empresa": f"Empresa Ficticia {rotulo}",
        "descricao": f"descricao ficticia {rotulo}",
        "local": "Sao Paulo",
    }
    base.update(campos)
    return VagaBruta(**base)


def _gravar(vagas: list[VagaBruta]) -> ResumoGravacao:
    with conectar("app") as conexao:
        return gravar_vagas(conexao, vagas)


def _contar(banco, rotulo: str) -> int:
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pleito.vaga WHERE id_externo LIKE %s", (f"teste-{rotulo}%",)
        )
        return cursor.fetchone()[0]


def test_gravar_duas_vezes_a_mesma_vaga_nao_duplica(banco, rotulo):
    vaga = _vaga(rotulo)
    assert _gravar([vaga]) == ResumoGravacao(recebidas=1, inseridas=1, duplicadas=0)
    assert _gravar([vaga]) == ResumoGravacao(recebidas=1, inseridas=0, duplicadas=1)
    assert _contar(banco, rotulo) == 1


def test_mesmo_conteudo_com_outro_id_externo_na_mesma_fonte_e_empresa_nao_duplica(banco, rotulo):
    assert _gravar([_vaga(rotulo, "a")]).inseridas == 1
    assert _gravar([_vaga(rotulo, "b")]).inseridas == 0
    assert _contar(banco, rotulo) == 1


def test_mesmo_conteudo_em_outra_fonte_e_vaga_distinta(banco, rotulo):
    assert _gravar([_vaga(rotulo, "a")]).inseridas == 1
    assert _gravar([_vaga(rotulo, "b", fonte="lever")]).inseridas == 1
    assert _contar(banco, rotulo) == 2


def test_empresa_e_reaproveitada_entre_vagas(banco, rotulo):
    _gravar([_vaga(rotulo, "a"), _vaga(rotulo, "b", titulo="Estagio em Backend")])
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT count(DISTINCT empresa_id) FROM pleito.vaga WHERE id_externo LIKE %s",
            (f"teste-{rotulo}%",),
        )
        assert cursor.fetchone()[0] == 1


def test_sql_em_titulo_e_empresa_fica_gravado_literalmente(banco, rotulo):
    vaga = _vaga(rotulo, titulo=ATAQUE, empresa=f"{ATAQUE} {rotulo}", descricao=ATAQUE)
    assert _gravar([vaga]).inseridas == 1
    with banco.cursor() as cursor:
        cursor.execute(
            """
            SELECT v.titulo, v.descricao, e.nome
            FROM pleito.vaga v JOIN pleito.empresa e ON e.id = v.empresa_id
            WHERE v.id_externo = %s
            """,
            (vaga.id_externo,),
        )
        assert cursor.fetchone() == (ATAQUE, ATAQUE, f"{ATAQUE} {rotulo}")
        cursor.execute("SELECT to_regclass('pleito.vaga') IS NOT NULL")
        assert cursor.fetchone()[0] is True


def test_papel_da_aplicacao_nao_apaga_vaga(banco, rotulo):
    psycopg = pytest.importorskip("psycopg")
    _gravar([_vaga(rotulo)])
    with conectar("app") as conexao, conexao.cursor() as cursor:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute("DELETE FROM vaga WHERE id_externo LIKE %s", (f"teste-{rotulo}%",))


def _privilegio(banco, consulta: str, *parametros) -> bool:
    with banco.cursor() as cursor:
        cursor.execute(consulta, parametros)
        return cursor.fetchone()[0]


def test_aplicacao_so_insere_o_nome_da_empresa(banco):
    for privilegio in ("UPDATE", "DELETE", "TRUNCATE"):
        assert not _privilegio(
            banco, "SELECT has_table_privilege('pleito_app', 'pleito.empresa', %s)", privilegio
        )
    for coluna in ("alvo", "dominio", "porte", "setor", "pais"):
        assert not _privilegio(
            banco,
            "SELECT has_column_privilege('pleito_app', 'pleito.empresa', %s, 'INSERT')",
            coluna,
        )
        assert not _privilegio(
            banco,
            "SELECT has_column_privilege('pleito_app', 'pleito.empresa', %s, 'UPDATE')",
            coluna,
        )
    assert _privilegio(
        banco,
        "SELECT has_column_privilege('pleito_app', 'pleito.empresa', 'nome', 'INSERT')",
    )


def test_sequencia_da_empresa_so_concede_uso_a_aplicacao(banco):
    assert _privilegio(
        banco,
        "SELECT has_sequence_privilege('pleito_app', 'pleito.empresa_id_seq', 'USAGE')",
    )
    for privilegio in ("SELECT", "UPDATE"):
        assert not _privilegio(
            banco,
            "SELECT has_sequence_privilege('pleito_app', 'pleito.empresa_id_seq', %s)",
            privilegio,
        )


def test_aplicacao_nao_atualiza_nem_apaga_empresa(banco, rotulo):
    psycopg = pytest.importorskip("psycopg")
    _gravar([_vaga(rotulo)])
    for comando in (
        "UPDATE empresa SET alvo = true WHERE nome_norm LIKE %s",
        "UPDATE empresa SET nome = 'x' WHERE nome_norm LIKE %s",
        "DELETE FROM empresa WHERE nome_norm LIKE %s",
    ):
        with conectar("app") as conexao, conexao.cursor() as cursor:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cursor.execute(comando, (f"%{rotulo}%",))
