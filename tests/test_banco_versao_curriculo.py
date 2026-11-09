from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid

import pytest
from psycopg import sql

from src.config import carregar
from src.db.versao_curriculo import (
    NovaVersao,
    Origem,
    historico_da_vaga,
    registrar_versao,
)


@pytest.fixture
def transacao(banco):
    with banco.cursor() as cursor:
        cursor.execute("SET search_path TO pleito, public")
    yield banco
    banco.rollback()


def como(conexao, papel: str, comando: str, parametros: tuple = ()) -> tuple[list, int]:
    with conexao.transaction(), conexao.cursor() as cursor:
        cursor.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(papel)))
        cursor.execute(comando, parametros)
        linhas = cursor.fetchall() if cursor.description else []
        quantidade = cursor.rowcount
        cursor.execute("RESET ROLE")
    return linhas, quantidade


def como_dono(conexao, comando: str, parametros: tuple = ()) -> list:
    with conexao.transaction(), conexao.cursor() as cursor:
        cursor.execute(comando, parametros)
        return cursor.fetchall() if cursor.description else []


def _vaga(conexao, estado: str = "variante_gerada") -> int:
    identificador = uuid.uuid4().hex
    return como_dono(
        conexao,
        """
        INSERT INTO pleito.vaga (fonte_id, id_externo, url, titulo, hash_conteudo, estado)
        VALUES (
            (SELECT id FROM pleito.fonte WHERE slug = 'greenhouse'),
            %s, 'https://example.invalid/vaga', 'Vaga ficticia', %s, %s::pleito.estado_vaga
        )
        RETURNING id
        """,
        (f"teste-versao-{identificador}", hashlib.sha256(identificador.encode()).digest(), estado),
    )[0][0]


def _hash(vaga_id: int, numero: int) -> bytes:
    return hashlib.sha256(f"{vaga_id}-{numero}".encode()).digest()


def _comando_versao(
    vaga_id: int, numero: int, origem: str = "gerada", paginas: int = 1
) -> tuple[str, tuple]:
    return (
        """
        INSERT INTO pleito.versao_curriculo (
            vaga_id, familia, idioma, numero, caminho_tex, caminho_pdf, hash_pdf, paginas,
            prompt_versao, modelo, origem
        )
        VALUES (%s, 'dados', 'pt', %s, 'cv.tex', 'cv.pdf', %s, %s, 'prompt-v1', 'modelo-x',
                %s::pleito.origem_versao)
        RETURNING id
        """,
        (vaga_id, numero, _hash(vaga_id, numero), paginas, origem),
    )


def _versao(conexao, vaga_id: int, numero: int, papel: str = "pleito_app", **campos) -> int:
    comando, parametros = _comando_versao(vaga_id, numero, **campos)
    return como(conexao, papel, comando, parametros)[0][0][0]


def _aprovar(conexao, vaga_id: int, versao_id: int, numero: int, papel: str = "pleito_painel"):
    return como(
        conexao,
        papel,
        """
        INSERT INTO pleito.aprovacao (vaga_id, versao_id, hash_aprovado, expira_em)
        VALUES (%s, %s, %s, now() + interval '1 day')
        RETURNING id
        """,
        (vaga_id, versao_id, _hash(vaga_id, numero)),
    )[0][0][0]


def _invalidada(conexao, aprovacao_id: int) -> tuple:
    return como_dono(
        conexao,
        """
        SELECT invalidada_em IS NOT NULL, invalidada_por_versao_id
        FROM pleito.aprovacao WHERE id = %s
        """,
        (aprovacao_id,),
    )[0]


def _estado(conexao, vaga_id: int) -> str:
    return como_dono(conexao, "SELECT estado::text FROM pleito.vaga WHERE id = %s", (vaga_id,))[0][
        0
    ]


def _pode(conexao, papel: str, tabela: str, privilegio: str, coluna: str | None = None) -> bool:
    with conexao.cursor() as cursor:
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


def test_versao_guarda_vaga_numero_nivel_hash_prompt_modelo_origem_e_regras(transacao):
    vaga_id = _vaga(transacao)
    nova = NovaVersao(
        vaga_id=vaga_id,
        familia="dados",
        idioma="pt",
        caminho_tex="dados/vagas/1/cv.tex",
        caminho_pdf="dados/vagas/1/cv.pdf",
        hash_pdf=_hash(vaga_id, 1),
        paginas=1,
        linhas_livres=None,
        validacao={"aprovado": True, "bloqueios": [], "indicios": ["V12"]},
        prompt_versao="gerar_slots-v3",
        modelo="modelo-forte-x",
        origem=Origem.GERADA,
    )
    como_dono(transacao, "SET LOCAL ROLE pleito_app")
    registro = registrar_versao(transacao, nova)
    como_dono(transacao, "RESET ROLE")
    assert registro.numero == 1
    linhas = como(
        transacao,
        "pleito_painel",
        """
        SELECT vaga_id, numero, nivel::text, hash_pdf, prompt_versao, modelo, caminho_pdf,
               validacao ->> 'aprovado', origem::text
        FROM pleito.versao_curriculo WHERE id = %s
        """,
        (registro.id,),
    )[0]
    assert linhas == [
        (
            vaga_id,
            1,
            "base",
            _hash(vaga_id, 1),
            "gerar_slots-v3",
            "modelo-forte-x",
            "dados/vagas/1/cv.pdf",
            "true",
            "gerada",
        )
    ]


def test_registrar_versao_numera_a_sequencia_da_vaga(transacao):
    vaga_id = _vaga(transacao)
    como_dono(transacao, "SET LOCAL ROLE pleito_app")
    numeros = []
    for _ in range(3):
        numeros.append(
            registrar_versao(
                transacao,
                NovaVersao(
                    vaga_id=vaga_id,
                    familia="dados",
                    idioma="pt",
                    caminho_tex="cv.tex",
                    caminho_pdf="cv.pdf",
                    hash_pdf=hashlib.sha256(uuid.uuid4().bytes).digest(),
                    paginas=1,
                    linhas_livres=None,
                    validacao={},
                    prompt_versao="p",
                    modelo="m",
                    origem=Origem.REFEITA,
                ),
            ).numero
        )
    como_dono(transacao, "RESET ROLE")
    assert numeros == [1, 2, 3]


def test_numero_nao_repete_nem_pula_dentro_da_vaga(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao)
    _versao(transacao, vaga_id, 1)
    for numero in (1, 3):
        comando, parametros = _comando_versao(vaga_id, numero)
        with pytest.raises(psycopg.errors.Error):
            como(transacao, "pleito_app", comando, parametros)
    _versao(transacao, vaga_id, 2)


def test_constraint_de_uma_pagina_segue_no_banco_para_todos_os_papeis(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    comando, parametros = _comando_versao(vaga_id, 1, paginas=2)
    with pytest.raises(psycopg.errors.CheckViolation):
        como_dono(transacao, comando, parametros)
    for papel, origem in (("pleito_app", "gerada"), ("pleito_chat", "chat")):
        comando, parametros = _comando_versao(vaga_id, 1, origem=origem, paginas=2)
        with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.CheckViolation)):
            como(transacao, papel, comando, parametros)
    comando, parametros = _comando_versao(vaga_id, 1, paginas=0)
    with pytest.raises(psycopg.errors.CheckViolation):
        como_dono(transacao, comando, parametros)


def test_versao_e_imutavel_ate_para_o_dono_do_banco(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao)
    versao_id = _versao(transacao, vaga_id, 1)
    alteracoes = (
        "hash_pdf = '\\x00'::bytea",
        "caminho_pdf = 'outro.pdf'",
        "caminho_tex = 'outro.tex'",
        "validacao = '{\"aprovado\": true}'::jsonb",
        "numero = 9",
        "vaga_id = NULL",
        "prompt_versao = 'outro'",
        "modelo = 'outro'",
        "origem = 'chat'",
        "paginas = 1, familia = 'backend'",
    )
    for alteracao in alteracoes:
        with pytest.raises(psycopg.errors.RestrictViolation):
            como_dono(
                transacao,
                sql.SQL("UPDATE pleito.versao_curriculo SET {} WHERE id = %s").format(
                    sql.SQL(alteracao)
                ),
                (versao_id,),
            )
    como_dono(
        transacao,
        "UPDATE pleito.versao_curriculo SET nivel = 'forte', protegida = true WHERE id = %s",
        (versao_id,),
    )
    for papel in ("pleito_app", "pleito_painel", "pleito_chat", "pleito_leitura"):
        assert not _pode(transacao, papel, "versao_curriculo", "UPDATE")
        for coluna in ("hash_pdf", "nivel", "protegida"):
            assert not _pode(transacao, papel, "versao_curriculo", "UPDATE", coluna)
        assert not _pode(transacao, papel, "versao_curriculo", "DELETE")


def test_nova_versao_invalida_a_aprovacao_da_anterior(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    _versao(transacao, vaga_id, 1)
    v2 = _versao(transacao, vaga_id, 2)
    aprovacao_id = _aprovar(transacao, vaga_id, v2, 2)
    como_dono(transacao, "UPDATE pleito.vaga SET estado = 'aprovada' WHERE id = %s", (vaga_id,))
    assert _invalidada(transacao, aprovacao_id) == (False, None)

    v3 = _versao(transacao, vaga_id, 3, origem="refeita")

    assert _invalidada(transacao, aprovacao_id) == (True, v3)
    assert _estado(transacao, vaga_id) == "aguardando_aprovacao"
    consumo = como(
        transacao,
        "pleito_app",
        "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
        (aprovacao_id,),
    )
    assert consumo[1] == 0
    auditoria = como_dono(
        transacao,
        """
        SELECT acao, entidade_id FROM pleito.auditoria
        WHERE entidade = 'aprovacao' AND entidade_id = %s
        """,
        (str(aprovacao_id),),
    )
    assert auditoria == [("invalidar_aprovacao", str(aprovacao_id))]
    marcadas = como(
        transacao,
        "pleito_painel",
        """
        SELECT numero, aprovada FROM pleito.historico_versao_curriculo
        WHERE vaga_id = %s ORDER BY numero
        """,
        (vaga_id,),
    )[0]
    assert marcadas == [(1, False), (2, False), (3, False)]


def test_versao_de_outra_vaga_nao_invalida_aprovacao(transacao):
    vaga_a = _vaga(transacao, "aguardando_aprovacao")
    vaga_b = _vaga(transacao, "aguardando_aprovacao")
    va1 = _versao(transacao, vaga_a, 1)
    _versao(transacao, vaga_b, 1)
    aprovacao_a = _aprovar(transacao, vaga_a, va1, 1)
    _versao(transacao, vaga_b, 2)
    assert _invalidada(transacao, aprovacao_a) == (False, None)


def test_aprovacao_consumida_antes_da_nova_versao_continua_como_foi_gravada(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    como(
        transacao,
        "pleito_app",
        "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
        (aprovacao_id,),
    )
    _versao(transacao, vaga_id, 2)
    assert _invalidada(transacao, aprovacao_id) == (False, None)


def test_aprovacao_so_vale_para_a_ultima_versao_com_o_hash_dela(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    v2 = _versao(transacao, vaga_id, 2)
    with pytest.raises(psycopg.errors.CheckViolation):
        _aprovar(transacao, vaga_id, v1, 1)
    with pytest.raises(psycopg.errors.CheckViolation):
        _aprovar(transacao, vaga_id, v2, 1)
    outra_vaga = _vaga(transacao, "aguardando_aprovacao")
    with pytest.raises(psycopg.errors.CheckViolation):
        _aprovar(transacao, outra_vaga, v2, 2)
    assert _aprovar(transacao, vaga_id, v2, 2)


def test_aprovacao_invalidada_nao_basta_para_criar_candidatura(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    como(
        transacao,
        "pleito_app",
        "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
        (aprovacao_id,),
    )
    como_dono(
        transacao,
        "UPDATE pleito.aprovacao SET invalidada_em = now() WHERE id = %s",
        (aprovacao_id,),
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        como(
            transacao,
            "pleito_app",
            """
            INSERT INTO pleito.candidatura (vaga_id, versao_id, aprovacao_id, plataforma)
            VALUES (%s, %s, %s, 'greenhouse')
            """,
            (vaga_id, v1, aprovacao_id),
        )


def test_chat_escreve_versao_e_nunca_aprovacao(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    v2 = _versao(transacao, vaga_id, 2, papel="pleito_chat", origem="chat")
    assert v2

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _aprovar(transacao, vaga_id, v2, 2, papel="pleito_chat")
    for comando in (
        "UPDATE pleito.aprovacao SET consumida_em = now() WHERE false",
        "UPDATE pleito.aprovacao SET invalidada_em = now() WHERE false",
        "DELETE FROM pleito.aprovacao WHERE false",
        "SELECT 1 FROM pleito.aprovacao",
        "INSERT INTO pleito.candidatura (vaga_id, versao_id, aprovacao_id, plataforma) "
        "VALUES (1, 1, 1, 'x')",
        "UPDATE pleito.vaga SET estado = 'aprovada' WHERE false",
        "UPDATE pleito.versao_curriculo SET nivel = 'campeao' WHERE false",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            como(transacao, "pleito_chat", comando)
    assert v1


def test_origem_da_versao_depende_do_papel(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _versao(transacao, vaga_id, 1, papel="pleito_chat", origem="gerada")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _versao(transacao, vaga_id, 1, papel="pleito_chat", origem="refeita")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _versao(transacao, vaga_id, 1, papel="pleito_app", origem="chat")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _versao(transacao, vaga_id, 1, papel="pleito_painel")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _versao(transacao, vaga_id, 1, papel="pleito_leitura")
    assert _versao(transacao, vaga_id, 1, papel="pleito_app", origem="refeita")


def test_grants_de_versao_por_papel(transacao):
    colunas_do_gerador = (
        "vaga_id",
        "familia",
        "idioma",
        "numero",
        "caminho_tex",
        "caminho_pdf",
        "hash_pdf",
        "paginas",
        "linhas_livres",
        "validacao",
        "prompt_versao",
        "modelo",
        "origem",
    )
    for papel in ("pleito_app", "pleito_chat"):
        assert not _pode(transacao, papel, "versao_curriculo", "INSERT")
        for coluna in colunas_do_gerador:
            assert _pode(transacao, papel, "versao_curriculo", "INSERT", coluna)
        for coluna in ("id", "nivel", "protegida", "criada_em"):
            assert not _pode(transacao, papel, "versao_curriculo", "INSERT", coluna)
    assert not _pode(transacao, "pleito_chat", "auditoria", "INSERT")
    for coluna in ("ator", "acao", "entidade", "entidade_id", "antes", "depois"):
        assert not _pode(transacao, "pleito_chat", "auditoria", "INSERT", coluna)
    for papel in ("pleito_painel", "pleito_leitura"):
        assert _pode(transacao, papel, "versao_curriculo", "SELECT")
        assert not _pode(transacao, papel, "versao_curriculo", "INSERT", "hash_pdf")
    assert _pode(transacao, "pleito_painel", "aprovacao", "INSERT", "versao_id")
    assert not _pode(transacao, "pleito_painel", "aprovacao", "INSERT", "invalidada_em")
    assert not _pode(transacao, "pleito_app", "aprovacao", "INSERT", "versao_id")
    assert not _pode(transacao, "pleito_app", "aprovacao", "UPDATE", "invalidada_em")
    assert not _pode(transacao, "pleito_painel", "aprovacao", "UPDATE", "invalidada_em")
    assert _pode(transacao, "pleito_chat", "versao_curriculo", "SELECT")
    assert _pode(transacao, "pleito_chat", "vaga", "SELECT")
    assert not _pode(transacao, "pleito_chat", "aprovacao", "SELECT")
    assert not _pode(transacao, "pleito_chat", "candidatura", "SELECT")
    assert not _pode(transacao, "pleito_chat", "aprovacao", "INSERT")
    assert not _pode(transacao, "pleito_chat", "aprovacao", "UPDATE")
    assert not _pode(transacao, "pleito_chat", "flag_sistema", "SELECT")


def test_papel_do_chat_nao_tem_login_nem_superuser(transacao):
    with transacao.cursor() as cursor:
        cursor.execute("SELECT rolcanlogin, rolsuper FROM pg_roles WHERE rolname = 'pleito_chat'")
        assert cursor.fetchone() == (False, False)


def test_historico_marca_a_versao_aprovada_e_a_enviada(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    v2 = _versao(transacao, vaga_id, 2, papel="pleito_chat", origem="chat")
    aprovacao_id = _aprovar(transacao, vaga_id, v2, 2)
    como(
        transacao,
        "pleito_app",
        "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
        (aprovacao_id,),
    )
    como_dono(
        transacao,
        """
        INSERT INTO pleito.candidatura (vaga_id, versao_id, aprovacao_id, plataforma)
        VALUES (%s, %s, %s, 'greenhouse')
        """,
        (vaga_id, v2, aprovacao_id),
    )
    for papel in ("pleito_painel", "pleito_app", "pleito_leitura"):
        linhas = como(
            transacao,
            papel,
            """
            SELECT numero, origem::text, aprovada, enviada
            FROM pleito.historico_versao_curriculo
            WHERE vaga_id = %s ORDER BY numero
            """,
            (vaga_id,),
        )[0]
        if papel == "pleito_leitura":
            assert [(n, o) for n, o, _, _ in linhas] == [(1, "gerada"), (2, "chat")]
        else:
            assert linhas == [(1, "gerada", False, False), (2, "chat", True, True)]
    assert v1


def test_aprovacao_expirada_nao_marca_a_versao_como_aprovada(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    como_dono(
        transacao,
        "UPDATE pleito.aprovacao SET criada_em = now() - interval '3 days', "
        "expira_em = now() - interval '1 day' WHERE id = %s",
        (aprovacao_id,),
    )
    historico = como(
        transacao,
        "pleito_painel",
        "SELECT aprovada FROM pleito.historico_versao_curriculo WHERE vaga_id = %s",
        (vaga_id,),
    )[0]
    assert historico == [(False,)]


def test_historico_da_vaga_pelo_modulo_lista_em_ordem_com_marcas(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    _versao(transacao, vaga_id, 1)
    v2 = _versao(transacao, vaga_id, 2, origem="refeita")
    _aprovar(transacao, vaga_id, v2, 2)
    outra = _vaga(transacao)
    _versao(transacao, outra, 1)
    como_dono(transacao, "SET LOCAL ROLE pleito_painel")
    historico = historico_da_vaga(transacao, vaga_id)
    como_dono(transacao, "RESET ROLE")
    assert [(h.numero, h.origem, h.aprovada, h.enviada) for h in historico] == [
        (1, Origem.GERADA, False, False),
        (2, Origem.REFEITA, True, False),
    ]
    assert historico[0].hash_pdf == _hash(vaga_id, 1)
    assert historico[0].nivel == "base"


def _consumir(conexao, aprovacao_id: int) -> None:
    como(
        conexao,
        "pleito_app",
        "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
        (aprovacao_id,),
    )


def _candidatura(conexao, vaga_id: int, versao_id: int, aprovacao_id: int, papel="pleito_app"):
    return como(
        conexao,
        papel,
        """
        INSERT INTO pleito.candidatura (vaga_id, versao_id, aprovacao_id, plataforma)
        VALUES (%s, %s, %s, 'greenhouse')
        """,
        (vaga_id, versao_id, aprovacao_id),
    )


def _mudar_estado(conexao, vaga_id: int, estado: str, papel: str = "pleito_app") -> None:
    como(
        conexao,
        papel,
        "UPDATE pleito.vaga SET estado = %s::pleito.estado_vaga WHERE id = %s",
        (estado, vaga_id),
    )


def test_candidatura_exige_que_a_versao_seja_a_ultima_da_vaga(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _consumir(transacao, aprovacao_id)
    _versao(transacao, vaga_id, 2, papel="pleito_chat", origem="chat")
    with pytest.raises(psycopg.errors.CheckViolation):
        _candidatura(transacao, vaga_id, v1, aprovacao_id)


def test_candidatura_da_ultima_versao_aprovada_passa(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _consumir(transacao, aprovacao_id)
    assert _candidatura(transacao, vaga_id, v1, aprovacao_id)[1] == 1


def test_nova_versao_rebaixa_a_vaga_aprovada_mesmo_com_aprovacao_consumida(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _mudar_estado(transacao, vaga_id, "aprovada")
    _consumir(transacao, aprovacao_id)
    _versao(transacao, vaga_id, 2, origem="refeita")
    assert _estado(transacao, vaga_id) == "aguardando_aprovacao"
    assert _invalidada(transacao, aprovacao_id) == (False, None)


def test_vaga_so_vira_aprovada_com_aprovacao_valida_da_ultima_versao(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    with pytest.raises(psycopg.errors.Error) as erro:
        _mudar_estado(transacao, vaga_id, "aprovada")
    assert "transicao de estado recusada" in str(erro.value)
    assert "aprovacao" in str(erro.value)
    with pytest.raises(psycopg.errors.Error):
        como_dono(
            transacao,
            "UPDATE pleito.vaga SET estado = 'aprovada' WHERE id = %s",
            (vaga_id,),
        )
    v1 = _versao(transacao, vaga_id, 1)
    with pytest.raises(psycopg.errors.Error):
        _mudar_estado(transacao, vaga_id, "aprovada")
    aprovacao_v1 = _aprovar(transacao, vaga_id, v1, 1)
    _consumir(transacao, aprovacao_v1)
    _versao(transacao, vaga_id, 2)
    with pytest.raises(psycopg.errors.Error):
        _mudar_estado(transacao, vaga_id, "aprovada")
    v3 = _versao(transacao, vaga_id, 3)
    aprovacao_v3 = _aprovar(transacao, vaga_id, v3, 3)
    como_dono(
        transacao,
        "UPDATE pleito.aprovacao SET invalidada_em = now() WHERE id = %s",
        (aprovacao_v3,),
    )
    with pytest.raises(psycopg.errors.Error):
        _mudar_estado(transacao, vaga_id, "aprovada")


def test_vaga_vira_aprovada_com_aprovacao_valida_da_ultima_versao(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    _aprovar(transacao, vaga_id, v1, 1)
    _mudar_estado(transacao, vaga_id, "aprovada")
    assert _estado(transacao, vaga_id) == "aprovada"


def test_vaga_so_vira_aplicada_com_candidatura(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _mudar_estado(transacao, vaga_id, "aprovada")
    _consumir(transacao, aprovacao_id)
    with pytest.raises(psycopg.errors.Error) as erro:
        _mudar_estado(transacao, vaga_id, "aplicada_aguardando_confirmacao")
    assert "candidatura" in str(erro.value)
    _mudar_estado(transacao, vaga_id, "pendente")
    for destino in ("aplicada_aguardando_confirmacao", "aplicada_confirmada"):
        with pytest.raises(psycopg.errors.Error):
            _mudar_estado(transacao, vaga_id, destino)
    _candidatura(transacao, vaga_id, v1, aprovacao_id)
    _mudar_estado(transacao, vaga_id, "aplicada_aguardando_confirmacao")
    _mudar_estado(transacao, vaga_id, "aplicada_confirmada")
    _mudar_estado(transacao, vaga_id, "entrevista")
    assert _estado(transacao, vaga_id) == "entrevista"


def test_chat_nao_escreve_auditoria_mas_cada_versao_dele_deixa_linha_do_ator_chat(transacao):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        como(
            transacao,
            "pleito_chat",
            """
            INSERT INTO pleito.auditoria (ator, acao, entidade)
            VALUES ('painel', 'aprovar', 'aprovacao')
            """,
        )
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    _versao(transacao, vaga_id, 1)
    v2 = _versao(transacao, vaga_id, 2, papel="pleito_chat", origem="chat")
    linhas = como_dono(
        transacao,
        """
        SELECT ator, acao, entidade, depois ->> 'vaga_id', depois ->> 'numero'
        FROM pleito.auditoria
        WHERE entidade = 'versao_curriculo' AND entidade_id = %s
        """,
        (str(v2),),
    )
    assert linhas == [("chat", "criar_versao", "versao_curriculo", str(vaga_id), "2")]
    v1 = como_dono(
        transacao,
        "SELECT id FROM pleito.versao_curriculo WHERE vaga_id = %s AND numero = 1",
        (vaga_id,),
    )[0][0]
    assert not como_dono(
        transacao,
        "SELECT 1 FROM pleito.auditoria WHERE entidade = 'versao_curriculo' AND entidade_id = %s",
        (str(v1),),
    )


@pytest.mark.parametrize(
    "estado",
    (
        "descoberta",
        "triada",
        "pontuada",
        "variante_gerada",
        "rejeitada_pelo_filipe",
        "aplicada_aguardando_confirmacao",
        "aplicada_confirmada",
        "pendente",
        "entrevista",
        "encerrada",
    ),
)
def test_chat_so_grava_versao_em_vaga_aguardando_ou_aprovada(transacao, estado):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, estado)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _versao(transacao, vaga_id, 1, papel="pleito_chat", origem="chat")


@pytest.mark.parametrize("estado", ("aguardando_aprovacao", "aprovada"))
def test_chat_grava_versao_em_vaga_aguardando_ou_aprovada(transacao, estado):
    vaga_id = _vaga(transacao, estado)
    assert _versao(transacao, vaga_id, 1, papel="pleito_chat", origem="chat")


def test_chat_nao_grava_versao_sem_vaga(transacao):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        como(
            transacao,
            "pleito_chat",
            """
            INSERT INTO pleito.versao_curriculo (
                vaga_id, familia, idioma, numero, caminho_tex, caminho_pdf, hash_pdf, paginas,
                origem
            )
            VALUES (NULL, 'dados', 'pt', 1, 'a.tex', 'a.pdf', %s, 1, 'chat')
            """,
            (hashlib.sha256(b"sem-vaga").digest(),),
        )


def test_aprovacao_consumida_nao_basta_para_voltar_a_aprovada(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _consumir(transacao, aprovacao_id)
    with pytest.raises(psycopg.errors.Error) as erro:
        _mudar_estado(transacao, vaga_id, "aprovada")
    assert "aprovacao" in str(erro.value)


def test_aplicacao_nao_refaz_sozinha_o_ciclo_aprovada_aguardando_aprovada(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _mudar_estado(transacao, vaga_id, "aprovada")
    _consumir(transacao, aprovacao_id)
    _versao(transacao, vaga_id, 2, origem="refeita")
    assert _estado(transacao, vaga_id) == "aguardando_aprovacao"
    with pytest.raises(psycopg.errors.Error):
        _mudar_estado(transacao, vaga_id, "aprovada")
    v2 = como_dono(
        transacao,
        "SELECT id FROM pleito.versao_curriculo WHERE vaga_id = %s AND numero = 2",
        (vaga_id,),
    )[0][0]
    _aprovar(transacao, vaga_id, v2, 2)
    _mudar_estado(transacao, vaga_id, "aprovada")
    assert _estado(transacao, vaga_id) == "aprovada"


def test_historico_nao_marca_aprovada_a_versao_velha_sem_envio(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _consumir(transacao, aprovacao_id)
    _versao(transacao, vaga_id, 2, origem="refeita")
    marcas = como(
        transacao,
        "pleito_painel",
        """
        SELECT numero, aprovada, enviada FROM pleito.historico_versao_curriculo
        WHERE vaga_id = %s ORDER BY numero
        """,
        (vaga_id,),
    )[0]
    assert marcas == [(1, False, False), (2, False, False)]


def test_historico_mantem_aprovada_a_versao_velha_que_foi_enviada(transacao):
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    v1 = _versao(transacao, vaga_id, 1)
    aprovacao_id = _aprovar(transacao, vaga_id, v1, 1)
    _consumir(transacao, aprovacao_id)
    _candidatura(transacao, vaga_id, v1, aprovacao_id)
    _versao(transacao, vaga_id, 2, origem="refeita")
    marcas = como(
        transacao,
        "pleito_painel",
        """
        SELECT numero, aprovada, enviada FROM pleito.historico_versao_curriculo
        WHERE vaga_id = %s ORDER BY numero
        """,
        (vaga_id,),
    )[0]
    assert marcas == [(1, True, True), (2, False, False)]


def _conexao_nova(papel: str):
    psycopg = pytest.importorskip("psycopg")
    conexao = psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT")),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    with conexao.cursor() as cursor:
        cursor.execute("SET search_path TO pleito, public")
        cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(papel)))
    conexao.commit()
    return conexao


@pytest.fixture
def vaga_comitada_em_banco_isolado(banco):
    criadas = []

    def criar(estado: str, versoes: int = 1) -> tuple[int, list[int]]:
        vaga_id = _vaga(banco, estado)
        criadas.append(vaga_id)
        banco.commit()
        ids = [_versao(banco, vaga_id, numero) for numero in range(1, versoes + 1)]
        banco.commit()
        return vaga_id, ids

    yield criar
    banco.rollback()
    apagar_no_banco_isolado(banco, criadas)


def apagar_no_banco_isolado(banco, vagas: list[int]) -> None:
    with banco.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM pleito.auditoria
            WHERE entidade IN ('aprovacao', 'versao_curriculo')
              AND entidade_id IN (
                  SELECT id::text FROM pleito.aprovacao WHERE vaga_id = ANY(%s)
                  UNION
                  SELECT id::text FROM pleito.versao_curriculo WHERE vaga_id = ANY(%s)
              )
            """,
            (vagas, vagas),
        )
        cursor.execute("DELETE FROM pleito.vaga WHERE id = ANY(%s)", (vagas,))
    banco.commit()


class Tentativa(threading.Thread):
    def __init__(self, comando: str, parametros: tuple, papel: str = "pleito_app"):
        super().__init__(daemon=True)
        self.comando = comando
        self.parametros = parametros
        self.papel = papel
        self.erro = None
        self.concluida = False

    def run(self):
        conexao = _conexao_nova(self.papel)
        try:
            with conexao.cursor() as cursor:
                cursor.execute("SET lock_timeout = '15s'")
                cursor.execute(self.comando, self.parametros)
            conexao.commit()
        except Exception as erro:
            self.erro = erro
        finally:
            self.concluida = True
            conexao.close()


def _comitada_aprovacao(banco, vaga_id: int, versao_id: int, numero: int, consumir: bool) -> int:
    aprovacao_id = _aprovar(banco, vaga_id, versao_id, numero)
    if consumir:
        _consumir(banco, aprovacao_id)
    banco.commit()
    return aprovacao_id


def test_candidatura_da_versao_velha_espera_a_versao_nova_e_e_recusada(
    banco, vaga_comitada_em_banco_isolado
):
    psycopg = pytest.importorskip("psycopg")
    vaga_id, (v1,) = vaga_comitada_em_banco_isolado("aguardando_aprovacao")
    aprovacao_id = _comitada_aprovacao(banco, vaga_id, v1, 1, consumir=True)
    gravando = _conexao_nova("pleito_app")
    try:
        comando, parametros = _comando_versao(vaga_id, 2, origem="refeita")
        with gravando.cursor() as cursor:
            cursor.execute(comando, parametros)
        candidatura = Tentativa(
            """
            INSERT INTO pleito.candidatura (vaga_id, versao_id, aprovacao_id, plataforma)
            VALUES (%s, %s, %s, 'greenhouse')
            """,
            (vaga_id, v1, aprovacao_id),
        )
        candidatura.start()
        time.sleep(1.0)
        assert not candidatura.concluida
        gravando.commit()
        candidatura.join(20)
    finally:
        gravando.close()
    assert candidatura.concluida
    assert isinstance(candidatura.erro, psycopg.errors.CheckViolation)
    with banco.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pleito.candidatura WHERE vaga_id = %s", (vaga_id,))
        assert cursor.fetchone()[0] == 0
    banco.rollback()


def test_vaga_aprovada_espera_a_versao_nova_e_e_recusada(banco, vaga_comitada_em_banco_isolado):
    psycopg = pytest.importorskip("psycopg")
    vaga_id, (v1,) = vaga_comitada_em_banco_isolado("aguardando_aprovacao")
    _comitada_aprovacao(banco, vaga_id, v1, 1, consumir=False)
    gravando = _conexao_nova("pleito_app")
    try:
        comando, parametros = _comando_versao(vaga_id, 2, origem="refeita")
        with gravando.cursor() as cursor:
            cursor.execute(comando, parametros)
        mudanca = Tentativa(
            "UPDATE pleito.vaga SET estado = 'aprovada' WHERE id = %s",
            (vaga_id,),
        )
        mudanca.start()
        time.sleep(1.0)
        assert not mudanca.concluida
        gravando.commit()
        mudanca.join(20)
    finally:
        gravando.close()
    assert mudanca.concluida
    assert isinstance(mudanca.erro, psycopg.errors.CheckViolation)
    with banco.cursor() as cursor:
        cursor.execute("SELECT estado::text FROM pleito.vaga WHERE id = %s", (vaga_id,))
        assert cursor.fetchone()[0] == "aguardando_aprovacao"
    banco.rollback()


def test_duas_versoes_simultaneas_na_mesma_vaga_nao_geram_o_mesmo_numero(
    banco, vaga_comitada_em_banco_isolado
):
    psycopg = pytest.importorskip("psycopg")
    vaga_id, _ = vaga_comitada_em_banco_isolado("aguardando_aprovacao")
    primeira = _conexao_nova("pleito_app")
    try:
        comando, parametros = _comando_versao(vaga_id, 2, origem="refeita")
        with primeira.cursor() as cursor:
            cursor.execute(comando, parametros)
        segunda = Tentativa(*_comando_versao(vaga_id, 2, origem="refeita"))
        segunda.start()
        time.sleep(1.0)
        assert not segunda.concluida
        primeira.commit()
        segunda.join(20)
    finally:
        primeira.close()
    assert isinstance(segunda.erro, psycopg.errors.CheckViolation)
    with banco.cursor() as cursor:
        cursor.execute(
            """
            SELECT array_agg(numero ORDER BY numero)
            FROM pleito.versao_curriculo WHERE vaga_id = %s
            """,
            (vaga_id,),
        )
        assert cursor.fetchone()[0] == [1, 2]
    banco.rollback()


@pytest.mark.parametrize("segunda_acao", ("candidatura", "estado"))
def test_consumir_aprovacao_e_gravar_versao_ao_mesmo_tempo_nao_da_deadlock(
    banco, vaga_comitada_em_banco_isolado, segunda_acao
):
    psycopg = pytest.importorskip("psycopg")
    vaga_id, (v1,) = vaga_comitada_em_banco_isolado("aguardando_aprovacao")
    aprovacao_id = _comitada_aprovacao(banco, vaga_id, v1, 1, consumir=False)
    _mudar_estado(banco, vaga_id, "aprovada")
    banco.commit()
    envio = _conexao_nova("pleito_app")
    try:
        with envio.cursor() as cursor:
            cursor.execute("SET lock_timeout = '15s'")
            cursor.execute(
                "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
                (aprovacao_id,),
            )
        comando, parametros = _comando_versao(vaga_id, 2, origem="refeita")
        nova_versao = Tentativa(comando, parametros)
        nova_versao.start()
        time.sleep(2.0)
        erro_do_envio = None
        try:
            with envio.cursor() as cursor:
                if segunda_acao == "candidatura":
                    cursor.execute(
                        """
                        INSERT INTO pleito.candidatura
                            (vaga_id, versao_id, aprovacao_id, plataforma)
                        VALUES (%s, %s, %s, 'greenhouse')
                        """,
                        (vaga_id, v1, aprovacao_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE pleito.vaga SET estado = 'pendente' WHERE id = %s", (vaga_id,)
                    )
            envio.commit()
        except psycopg.Error as erro:
            erro_do_envio = erro
            envio.rollback()
        nova_versao.join(20)
    finally:
        envio.close()
    assert not isinstance(erro_do_envio, psycopg.errors.DeadlockDetected)
    assert not isinstance(nova_versao.erro, psycopg.errors.DeadlockDetected)
    assert nova_versao.erro is None
    assert isinstance(erro_do_envio, psycopg.errors.CheckViolation)
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT array_agg(numero ORDER BY numero) FROM pleito.versao_curriculo "
            "WHERE vaga_id = %s",
            (vaga_id,),
        )
        assert cursor.fetchone()[0] == [1, 2]
        cursor.execute("SELECT count(*) FROM pleito.candidatura WHERE vaga_id = %s", (vaga_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT consumida_em IS NULL FROM pleito.aprovacao WHERE id = %s", (aprovacao_id,)
        )
        assert cursor.fetchone()[0] is True
        cursor.execute("SELECT estado::text FROM pleito.vaga WHERE id = %s", (vaga_id,))
        assert cursor.fetchone()[0] == "aguardando_aprovacao"
    banco.rollback()
    assert (
        como(
            banco,
            "pleito_app",
            "UPDATE pleito.aprovacao SET consumida_em = now() WHERE id = %s",
            (aprovacao_id,),
        )[1]
        == 0
    )
    banco.rollback()


def test_aprovacao_so_e_criada_depois_de_travar_a_vaga_e_ver_a_versao_nova(
    banco, vaga_comitada_em_banco_isolado
):
    psycopg = pytest.importorskip("psycopg")
    vaga_id, (v1,) = vaga_comitada_em_banco_isolado("aguardando_aprovacao")
    gravando = _conexao_nova("pleito_app")
    try:
        comando, parametros = _comando_versao(vaga_id, 2, origem="refeita")
        with gravando.cursor() as cursor:
            cursor.execute(comando, parametros)
        aprovacao = Tentativa(
            """
            INSERT INTO pleito.aprovacao (vaga_id, versao_id, hash_aprovado, expira_em)
            VALUES (%s, %s, %s, now() + interval '1 day')
            """,
            (vaga_id, v1, _hash(vaga_id, 1)),
            papel="pleito_painel",
        )
        aprovacao.start()
        time.sleep(1.0)
        assert not aprovacao.concluida
        gravando.commit()
        aprovacao.join(20)
    finally:
        gravando.close()
    assert isinstance(aprovacao.erro, psycopg.errors.CheckViolation)


TRANSICOES_VALIDAS = (
    ("descoberta", "triada"),
    ("triada", "pontuada"),
    ("pontuada", "variante_gerada"),
    ("variante_gerada", "aguardando_aprovacao"),
    ("aguardando_aprovacao", "rejeitada_pelo_filipe"),
    ("aprovada", "aguardando_aprovacao"),
    ("aprovada", "pendente"),
    ("aplicada_confirmada", "entrevista"),
    ("entrevista", "oferta"),
    ("oferta", "encerrada"),
)

TRANSICOES_RECUSADAS = (
    ("aguardando_aprovacao", "aplicada_aguardando_confirmacao"),
    ("aguardando_aprovacao", "aplicada_confirmada"),
    ("variante_gerada", "aprovada"),
    ("pontuada", "aprovada"),
    ("descoberta", "aprovada"),
    ("triada", "aguardando_aprovacao"),
    ("aprovada", "aplicada_confirmada"),
    ("rejeitada_pelo_filipe", "aprovada"),
    ("encerrada", "aprovada"),
    ("encerrada", "descoberta"),
    ("oferta", "triada"),
    ("entrevista", "aprovada"),
)


@pytest.mark.parametrize(("origem", "destino"), TRANSICOES_VALIDAS)
def test_transicao_prevista_na_maquina_de_estados_passa(transacao, origem, destino):
    vaga_id = _vaga(transacao, origem)
    como_dono(
        transacao,
        "UPDATE pleito.vaga SET estado = %s::pleito.estado_vaga WHERE id = %s",
        (destino, vaga_id),
    )
    assert _estado(transacao, vaga_id) == destino


@pytest.mark.parametrize(("origem", "destino"), TRANSICOES_RECUSADAS)
def test_transicao_fora_da_maquina_de_estados_e_recusada_no_banco(transacao, origem, destino):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, origem)
    with pytest.raises(psycopg.errors.Error) as erro:
        como_dono(
            transacao,
            "UPDATE pleito.vaga SET estado = %s::pleito.estado_vaga WHERE id = %s",
            (destino, vaga_id),
        )
    assert "transicao de estado recusada" in str(erro.value)


def test_transicao_recusada_vale_tambem_para_o_papel_da_aplicacao(transacao):
    psycopg = pytest.importorskip("psycopg")
    vaga_id = _vaga(transacao, "aguardando_aprovacao")
    with pytest.raises(psycopg.errors.Error) as erro:
        como(
            transacao,
            "pleito_app",
            "UPDATE pleito.vaga SET estado = 'aplicada_confirmada' WHERE id = %s",
            (vaga_id,),
        )
    assert "transicao de estado recusada" in str(erro.value)


def test_atualizar_outra_coluna_sem_mudar_estado_nao_aciona_a_maquina(transacao):
    vaga_id = _vaga(transacao, "encerrada")
    como_dono(transacao, "UPDATE pleito.vaga SET nota = 50 WHERE id = %s", (vaga_id,))
    como_dono(
        transacao,
        "UPDATE pleito.vaga SET estado = 'encerrada' WHERE id = %s",
        (vaga_id,),
    )
    assert _estado(transacao, vaga_id) == "encerrada"


def test_transicoes_do_config_de_email_existem_na_tabela_do_banco(transacao):
    configurada = carregar("eventos_email")
    esperadas = {
        (origem, destino)
        for etapa, destino in configurada["estado_por_etapa"].items()
        for origem in configurada["origens_permitidas"][destino]
    }
    permitidas = {
        tuple(linha)
        for linha in como_dono(
            transacao,
            "SELECT origem::text, destino::text FROM pleito.transicao_estado_vaga",
        )
    }
    assert esperadas
    assert esperadas <= permitidas


def test_toda_transicao_tem_estados_validos_e_nenhum_estado_sai_do_proprio(transacao):
    linhas = como_dono(
        transacao,
        "SELECT origem::text, destino::text FROM pleito.transicao_estado_vaga",
    )
    assert linhas
    assert all(origem != destino for origem, destino in linhas)
    assert not any(origem == "encerrada" for origem, _ in linhas)
