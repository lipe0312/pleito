from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.db.uso_llm import falhar_uso_llm, finalizar_uso_llm, reservar_uso_llm
from src.llm.orcamento import OrcamentoEsgotado, SaldoInsuficienteTierForte
from viabilidade.config import carregar


@pytest.fixture
def banco():
    if os.getenv("PLEITO_TEST_DATABASE") != "1":
        pytest.skip("testes de banco nao solicitados")
    host = os.getenv("POSTGRES_HOST")
    port = int(os.getenv("POSTGRES_PORT", "0"))
    dbname = os.getenv("POSTGRES_DB")
    if host not in {"127.0.0.1", "localhost"} or port != 55432:
        pytest.fail(
            "testes de banco so podem conectar ao Postgres isolado do pleito na porta 55432"
        )
    if dbname != "pleito":
        pytest.fail("testes de banco so podem conectar ao banco pleito")
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    ) as conexao:
        yield conexao


def _pode(banco, papel: str, tabela: str, privilegio: str, coluna: str | None = None) -> bool:
    with banco.cursor() as cursor:
        if coluna:
            cursor.execute(
                "SELECT has_column_privilege(%s, %s, %s, %s)",
                (papel, f"pleito.{tabela}", coluna, privilegio),
            )
        else:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (papel, f"pleito.{tabela}", privilegio),
            )
        return cursor.fetchone()[0]


def test_aplicacao_nao_altera_flag_do_sistema(banco):
    assert not _pode(banco, "pleito_app", "flag_sistema", "UPDATE", "ligada")
    assert _pode(banco, "pleito_painel", "flag_sistema", "UPDATE", "ligada")
    assert not _pode(banco, "pleito_painel", "flag_sistema", "UPDATE", "chave")
    assert not _pode(banco, "pleito_painel", "flag_sistema", "UPDATE", "alterada_em")


def test_painel_nao_altera_estado_da_vaga_ou_prova_de_candidatura(banco):
    assert not _pode(banco, "pleito_painel", "vaga", "UPDATE", "estado")
    assert not _pode(banco, "pleito_painel", "candidatura", "UPDATE", "prova")
    assert _pode(banco, "pleito_app", "candidatura", "UPDATE", "prova")


def test_aprovacao_e_auditoria_tem_escrita_separada(banco):
    assert not _pode(banco, "pleito_painel", "aprovacao", "INSERT")
    assert _pode(banco, "pleito_painel", "aprovacao", "INSERT", "vaga_id")
    assert not _pode(banco, "pleito_painel", "aprovacao", "INSERT", "id")
    assert not _pode(banco, "pleito_app", "aprovacao", "INSERT")
    assert _pode(banco, "pleito_app", "aprovacao", "UPDATE", "consumida_em")
    for papel in ("pleito_app", "pleito_painel"):
        assert not _pode(banco, papel, "auditoria", "INSERT")
        for coluna in ("ator", "acao", "entidade", "entidade_id", "antes", "depois"):
            assert _pode(banco, papel, "auditoria", "INSERT", coluna)
        assert not _pode(banco, papel, "auditoria", "INSERT", "ocorrido_em")
        assert not _pode(banco, papel, "auditoria", "UPDATE")
        assert not _pode(banco, papel, "auditoria", "DELETE")


def test_uso_llm_limita_escrita_aos_campos_necessarios(banco):
    assert _pode(banco, "pleito_app", "uso_llm", "INSERT", "etapa")
    assert not _pode(banco, "pleito_app", "uso_llm", "INSERT", "tokens_entrada")
    assert _pode(banco, "pleito_app", "uso_llm", "UPDATE", "tokens_entrada")
    assert not _pode(banco, "pleito_app", "uso_llm", "UPDATE", "modelo")
    assert not _pode(banco, "pleito_painel", "uso_llm", "UPDATE", "estado")
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with banco.transaction(), banco.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE pleito_app")
            cursor.execute("UPDATE pleito.uso_llm SET modelo = 'alterado' WHERE false")


def test_tabelas_sensiveis_mantem_rls(banco):
    tabelas = (
        "vaga",
        "versao_curriculo",
        "aprovacao",
        "candidatura",
        "evento_email",
        "flag_sistema",
        "resposta_banco",
        "uso_llm",
    )
    with banco.cursor() as cursor:
        cursor.execute(
            """
            SELECT relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'pleito' AND c.relrowsecurity
            """
        )
        com_rls = {registro[0] for registro in cursor.fetchall()}
    assert set(tabelas) <= com_rls


def test_reserva_llm_registra_uso_finalizacao_e_falha(banco):
    usos = []
    try:
        uso_id = reservar_uso_llm(
            "teste_fase_0",
            "openai",
            "modelo-teste",
            "rapido",
            "teste-v1",
            Decimal("0.000001"),
        )
        usos.append(uso_id)
        with banco.cursor() as cursor:
            cursor.execute(
                """
                SELECT prompt_versao, estado, custo_reservado_usd
                FROM pleito.uso_llm WHERE id = %s
                """,
                (uso_id,),
            )
            assert cursor.fetchone() == ("teste-v1", "reservado", Decimal("0.000001"))
        finalizar_uso_llm(
            uso_id,
            12,
            3,
            Decimal("0.000001"),
            "valida",
        )
        with banco.cursor() as cursor:
            cursor.execute(
                """
                SELECT tokens_entrada, tokens_saida, custo_usd, custo_reservado_usd,
                       resultado_validacao, estado
                FROM pleito.uso_llm
                WHERE id = %s
                """,
                (uso_id,),
            )
            assert cursor.fetchone() == (
                12,
                3,
                Decimal("0.000001"),
                Decimal("0"),
                "valida",
                "concluido",
            )
        with pytest.raises(RuntimeError):
            finalizar_uso_llm(uso_id, 12, 3, Decimal("0.000001"), "valida")

        falha_id = reservar_uso_llm(
            "teste_fase_0",
            "openai",
            "modelo-teste",
            "rapido",
            "teste-v1",
            Decimal("0.000001"),
        )
        usos.append(falha_id)
        falhar_uso_llm(falha_id, "ValueError")
        with banco.cursor() as cursor:
            cursor.execute(
                "SELECT custo_reservado_usd, estado, erro_tipo FROM pleito.uso_llm WHERE id = %s",
                (falha_id,),
            )
            assert cursor.fetchone() == (Decimal("0"), "falhou", "ValueError")
    finally:
        if usos:
            with banco.cursor() as cursor:
                cursor.execute("DELETE FROM pleito.uso_llm WHERE id = ANY(%s)", (usos,))
            banco.commit()


def test_orcamento_llm_recusa_reserva_acima_do_limite_diario(banco):
    diario = Decimal(str(carregar("limites")["llm"]["orcamento_usd_dia_max"]))
    with pytest.raises(OrcamentoEsgotado):
        reservar_uso_llm(
            "teste_fase_0",
            "openai",
            "modelo-teste",
            "rapido",
            "teste-v1",
            diario + Decimal("1"),
            agora=datetime(2000, 1, 1, tzinfo=UTC),
        )


def test_reserva_forte_identifica_saldo_baixo_para_fallback_seletivo(banco):
    with banco.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO pleito.uso_llm (
                etapa, provedor, modelo, tier, custo_usd, custo_reservado_usd, estado,
                ocorrido_em
            )
            VALUES (
                'teste_fase_0_5', 'openai', 'modelo-teste', 'forte', 4, 0, 'concluido',
                '2000-01-10T00:00:00+00:00'
            )
            RETURNING id
            """
        )
        uso_id = cursor.fetchone()[0]
    banco.commit()
    try:
        with pytest.raises(SaldoInsuficienteTierForte):
            reservar_uso_llm(
                "pontuacao_final",
                "openai",
                "modelo-forte",
                "forte",
                "teste-v1",
                Decimal("0.000001"),
                agora=datetime(2000, 1, 10, tzinfo=UTC),
            )
    finally:
        with banco.cursor() as cursor:
            cursor.execute("DELETE FROM pleito.uso_llm WHERE id = %s", (uso_id,))
        banco.commit()


def test_update_nao_autorizado_falha_no_postgres(banco):
    psycopg = pytest.importorskip("psycopg")
    ataques = (
        ("pleito_app", "UPDATE pleito.flag_sistema SET ligada = true WHERE false"),
        ("pleito_painel", "UPDATE pleito.flag_sistema SET chave = 'atacada' WHERE false"),
        ("pleito_painel", "UPDATE pleito.vaga SET estado = 'aplicada_confirmada' WHERE false"),
        ("pleito_app", "UPDATE pleito.auditoria SET acao = 'alterada' WHERE false"),
    )
    for papel, sql in ataques:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with banco.transaction(), banco.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {papel}")
                cursor.execute(sql)


def _preparar_aprovacao(banco, hash_aprovado: bytes | None = None) -> tuple[int, int, bytes]:
    identificador = uuid.uuid4().hex
    hash_pdf = hashlib.sha256(identificador.encode()).digest()
    hash_aprovado = hash_aprovado or hash_pdf
    with banco.cursor() as cursor:
        cursor.execute("SELECT id FROM pleito.fonte WHERE slug = %s", ("greenhouse",))
        fonte_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO pleito.vaga (fonte_id, id_externo, url, titulo, hash_conteudo)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (fonte_id, identificador, "https://example.invalid/vaga", "Teste", hash_pdf),
        )
        vaga_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO pleito.versao_curriculo (
                vaga_id, familia, idioma, caminho_tex, caminho_pdf, hash_pdf, paginas
            )
            VALUES (%s, 'dados', 'pt', 'teste.tex', 'teste.pdf', %s, 1)
            RETURNING id
            """,
            (vaga_id, hash_pdf),
        )
        versao_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO pleito.aprovacao (vaga_id, versao_id, hash_aprovado, expira_em)
            VALUES (%s, %s, %s, now() + interval '1 day')
            RETURNING id
            """,
            (vaga_id, versao_id, hash_aprovado),
        )
        aprovacao_id = cursor.fetchone()[0]
    return vaga_id, versao_id, aprovacao_id


def _inserir_candidatura(banco, vaga_id: int, versao_id: int, aprovacao_id: int) -> None:
    with banco.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO pleito.candidatura (vaga_id, versao_id, aprovacao_id, plataforma)
            VALUES (%s, %s, %s, 'greenhouse')
            """,
            (vaga_id, versao_id, aprovacao_id),
        )


def test_candidatura_requer_aprovacao_consumida(banco):
    psycopg = pytest.importorskip("psycopg")
    try:
        vaga_id, versao_id, aprovacao_id = _preparar_aprovacao(banco)
        with banco.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE pleito_app")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with banco.transaction():
                _inserir_candidatura(banco, vaga_id, versao_id, aprovacao_id)
        with banco.cursor() as cursor:
            cursor.execute(
                "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
                (aprovacao_id,),
            )
        _inserir_candidatura(banco, vaga_id, versao_id, aprovacao_id)
    finally:
        banco.rollback()


def test_candidatura_requer_hash_aprovado_igual_ao_pdf(banco):
    psycopg = pytest.importorskip("psycopg")
    try:
        vaga_id, versao_id, aprovacao_id = _preparar_aprovacao(banco, b"x" * 32)
        with banco.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE pleito_app")
            cursor.execute(
                "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
                (aprovacao_id,),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            _inserir_candidatura(banco, vaga_id, versao_id, aprovacao_id)
    finally:
        banco.rollback()
