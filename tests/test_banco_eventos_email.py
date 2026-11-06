from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from src.db.conexao import conectar
from src.email.classificador import classificar
from src.email.cursor import Cursor, gravar_cursor, ler_cursor
from src.email.eventos import politica
from src.email.modelo import Classificacao, Email, Etapa, Motivo
from src.email.organizador import configuracao_organizacao, rodada
from src.email.registro import RegistroNoBanco
from src.email.repositorio import EmailRecebido, ResultadoEvento, gravar_evento
from tests.test_email_organizador import GmailFalso, mensagem

APROVADA = "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
ATAQUE = "'; DROP TABLE evento_email; --"
RECEBIDO_EM = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def sufixo(banco):
    valor = uuid.uuid4().hex[:12]
    yield valor
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT id::text FROM pleito.evento_email WHERE id_mensagem LIKE %s",
            (f"teste-{valor}%",),
        )
        eventos = [linha[0] for linha in cursor.fetchall()]
        cursor.execute(
            "SELECT id::text FROM pleito.vaga WHERE id_externo LIKE %s", (f"teste-{valor}%",)
        )
        vagas = [linha[0] for linha in cursor.fetchall()]
        cursor.execute(
            """
            DELETE FROM pleito.auditoria
            WHERE (entidade = 'evento_email' AND entidade_id = ANY(%s))
               OR (entidade = 'vaga' AND entidade_id = ANY(%s))
            """,
            (eventos, vagas),
        )
        cursor.execute(
            "DELETE FROM pleito.evento_email WHERE id_mensagem LIKE %s", (f"teste-{valor}%",)
        )
        cursor.execute("DELETE FROM pleito.vaga WHERE id_externo LIKE %s", (f"teste-{valor}%",))
        cursor.execute("DELETE FROM pleito.empresa WHERE nome LIKE %s", (f"teste-{valor}%",))
    banco.commit()


def _vaga(banco, sufixo: str, estado: str) -> int:
    id_externo = f"teste-{sufixo}-{uuid.uuid4().hex[:6]}"
    with banco.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO pleito.vaga (fonte_id, id_externo, url, titulo, hash_conteudo, estado)
            VALUES (
                (SELECT id FROM pleito.fonte WHERE slug = 'greenhouse'),
                %s, 'https://exemplo.invalid/vaga', 'Vaga ficticia', %s,
                %s::pleito.estado_vaga
            )
            RETURNING id
            """,
            (id_externo, hashlib.sha256(id_externo.encode()).digest(), estado),
        )
        vaga_id = cursor.fetchone()[0]
    banco.commit()
    return vaga_id


def _recebido(sufixo: str, email: Email, chave: str = "m") -> EmailRecebido:
    return EmailRecebido(f"teste-{sufixo}-{chave}", email, RECEBIDO_EM)


def _entrevista() -> Email:
    return Email(
        "Gupy <no-reply@gupy.com.br>",
        "Convite para entrevista",
        "Gostariamos de agendar uma entrevista.",
        autenticacao=APROVADA,
    )


def _gravar(recebido: EmailRecebido, classificacao: Classificacao, vaga_id=None):
    with conectar("app") as conexao:
        return gravar_evento(conexao, recebido, classificacao, vaga_id)


def _estado(banco, vaga_id: int) -> str:
    with banco.cursor() as cursor:
        cursor.execute("SELECT estado::text FROM pleito.vaga WHERE id = %s", (vaga_id,))
        return cursor.fetchone()[0]


def _evento(banco, id_mensagem: str) -> tuple:
    with banco.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, tipo, aplicado, fila, autenticado, vaga_id
            FROM pleito.evento_email WHERE id_mensagem = %s
            """,
            (id_mensagem,),
        )
        return cursor.fetchone()


def _auditorias(banco, entidade: str, entidade_id: int) -> list[str]:
    with banco.cursor() as cursor:
        cursor.execute(
            """
            SELECT acao FROM pleito.auditoria
            WHERE entidade = %s AND entidade_id = %s ORDER BY id
            """,
            (entidade, str(entidade_id)),
        )
        return [linha[0] for linha in cursor.fetchall()]


def test_acima_do_limiar_muda_o_estado_da_vaga_e_audita_cada_escrita(banco, sufixo):
    vaga_id = _vaga(banco, sufixo, "aplicada_confirmada")
    email = _entrevista()
    recebido = _recebido(sufixo, email)
    resultado = _gravar(recebido, classificar(email), vaga_id)
    assert resultado.estado_anterior == "aplicada_confirmada"
    assert resultado.decisao.estado_novo == "entrevista"
    assert _estado(banco, vaga_id) == "entrevista"
    evento_id, tipo, aplicado, fila, autenticado, vinculada = _evento(banco, recebido.id_mensagem)
    assert (tipo, aplicado, fila, autenticado, vinculada) == (
        "entrevista",
        True,
        None,
        True,
        vaga_id,
    )
    assert _auditorias(banco, "evento_email", evento_id) == ["registrar_evento", "aplicar_evento"]
    assert _auditorias(banco, "vaga", vaga_id) == ["mudar_estado"]


def test_auditoria_registra_o_ator_do_config_e_o_estado_antes_e_depois(banco, sufixo):
    vaga_id = _vaga(banco, sufixo, "aplicada_confirmada")
    email = _entrevista()
    _gravar(_recebido(sufixo, email), classificar(email), vaga_id)
    with banco.cursor() as cursor:
        cursor.execute(
            """
            SELECT ator, antes ->> 'estado', depois ->> 'estado'
            FROM pleito.auditoria WHERE entidade = 'vaga' AND entidade_id = %s
            """,
            (str(vaga_id),),
        )
        assert cursor.fetchone() == (politica().ator, "aplicada_confirmada", "entrevista")


def test_mesma_mensagem_lida_de_novo_nao_duplica_evento_nem_auditoria(banco, sufixo):
    vaga_id = _vaga(banco, sufixo, "aplicada_confirmada")
    email = _entrevista()
    recebido = _recebido(sufixo, email)
    primeiro = _gravar(recebido, classificar(email), vaga_id)
    segundo = _gravar(recebido, classificar(email), vaga_id)
    assert not primeiro.duplicado
    assert segundo == ResultadoEvento(evento_id=None, duplicado=True)
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pleito.evento_email WHERE id_mensagem = %s",
            (recebido.id_mensagem,),
        )
        assert cursor.fetchone()[0] == 1
    assert len(_auditorias(banco, "evento_email", primeiro.evento_id)) == 2
    assert _auditorias(banco, "vaga", vaga_id) == ["mudar_estado"]


def test_abaixo_do_limiar_vai_para_classificar_sem_mudar_estado(banco, sufixo):
    vaga_id = _vaga(banco, sufixo, "aplicada_confirmada")
    recebido = _recebido(sufixo, _entrevista())
    classificacao = Classificacao(
        Etapa.ENTREVISTA, politica().limiar - 0.01, Motivo.RECONHECIDO, "gupy"
    )
    resultado = _gravar(recebido, classificacao, vaga_id)
    assert resultado.decisao.fila is Etapa.CLASSIFICAR
    assert _estado(banco, vaga_id) == "aplicada_confirmada"
    evento_id, _, aplicado, fila, _, _ = _evento(banco, recebido.id_mensagem)
    assert (aplicado, fila) == (False, "classificar")
    assert _auditorias(banco, "evento_email", evento_id) == ["registrar_evento"]
    assert _auditorias(banco, "vaga", vaga_id) == []


def test_sem_vaga_associada_vai_para_classificar(banco, sufixo):
    email = _entrevista()
    recebido = _recebido(sufixo, email)
    _gravar(recebido, classificar(email))
    _, _, aplicado, fila, _, vinculada = _evento(banco, recebido.id_mensagem)
    assert (aplicado, fila, vinculada) == (False, "classificar", None)


def test_remetente_forjado_vai_para_suspeitos_e_nao_muda_estado(banco, sufixo):
    vaga_id = _vaga(banco, sufixo, "entrevista")
    email = Email(
        "Gupy <no-reply@gupy-vagas.com.br>",
        "Proposta de emprego",
        "Temos o prazer de oferecer. Envie seus dados bancarios.",
        autenticacao=APROVADA,
    )
    classificacao = classificar(email)
    assert classificacao.etapa is Etapa.SUSPEITO
    recebido = _recebido(sufixo, email)
    _gravar(recebido, classificacao, vaga_id)
    assert _estado(banco, vaga_id) == "entrevista"
    _, tipo, aplicado, fila, autenticado, _ = _evento(banco, recebido.id_mensagem)
    assert (tipo, aplicado, fila, autenticado) == ("suspeito", False, "suspeito", False)


def test_sql_no_id_e_no_remetente_fica_gravado_literalmente(banco, sufixo):
    email = Email(f"{ATAQUE} <rh@empresaficticia.invalid>", ATAQUE, ATAQUE, autenticacao=APROVADA)
    recebido = _recebido(sufixo, email, ATAQUE)
    _gravar(recebido, classificar(email))
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT id_mensagem FROM pleito.evento_email WHERE id_mensagem = %s",
            (recebido.id_mensagem,),
        )
        assert cursor.fetchone()[0] == recebido.id_mensagem
        cursor.execute("SELECT to_regclass('pleito.evento_email') IS NOT NULL")
        assert cursor.fetchone()[0] is True


def _pode(banco, papel: str, privilegio: str, coluna: str | None = None) -> bool:
    with banco.cursor() as cursor:
        if coluna:
            cursor.execute(
                "SELECT has_column_privilege(%s, 'pleito.evento_email', %s, %s)",
                (papel, coluna, privilegio),
            )
        else:
            cursor.execute(
                "SELECT has_table_privilege(%s, 'pleito.evento_email', %s)", (papel, privilegio)
            )
        return cursor.fetchone()[0]


def test_aplicacao_grava_a_fila_mas_so_atualiza_aplicado(banco):
    assert _pode(banco, "pleito_app", "INSERT", "fila")
    assert _pode(banco, "pleito_app", "UPDATE", "aplicado")
    for coluna in ("fila", "tipo", "confianca", "autenticado", "vaga_id", "id_mensagem"):
        assert not _pode(banco, "pleito_app", "UPDATE", coluna)
    assert not _pode(banco, "pleito_app", "INSERT", "aplicado")
    for papel in ("pleito_app", "pleito_painel", "pleito_leitura"):
        assert not _pode(banco, papel, "DELETE")
        assert not _pode(banco, papel, "TRUNCATE")
    for papel in ("pleito_painel", "pleito_leitura"):
        assert not _pode(banco, papel, "INSERT", "fila")
        assert not _pode(banco, papel, "UPDATE", "aplicado")


def test_estados_de_destino_do_config_existem_no_enum_do_banco(banco):
    with banco.cursor() as cursor:
        cursor.execute("SELECT unnest(enum_range(NULL::pleito.estado_vaga))::text")
        existentes = {linha[0] for linha in cursor.fetchall()}
    configurada = politica()
    destinos = set(configurada.estado_por_etapa.values())
    origens = {o for lista in configurada.origens_permitidas.values() for o in lista}
    assert destinos | origens <= existentes


def _inserir_como_app(
    id_mensagem: str,
    autenticado: bool,
    confianca: str,
    fila: str | None,
    tipo: str = "oferta",
):
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO evento_email (
                id_mensagem, remetente, autenticado, tipo, confianca, recebido_em, fila
            )
            VALUES (%s, 'x@exemplo.invalid', %s, %s, %s, now(), %s)
            RETURNING id
            """,
            (id_mensagem, autenticado, tipo, confianca, fila),
        )
        return cursor.fetchone()[0]


def test_rls_recusa_evento_nao_autenticado_com_confianca_maxima_fora_de_fila(sufixo):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _inserir_como_app(f"teste-{sufixo}-rls", False, "1.00", None)
    assert _inserir_como_app(f"teste-{sufixo}-suspeito", False, "1.00", "suspeito", "suspeito")
    assert _inserir_como_app(f"teste-{sufixo}-classificar", False, "1.00", "classificar")


def test_nao_autenticado_com_confianca_maxima_e_gravado_na_fila_classificar(banco, sufixo):
    vaga_id = _vaga(banco, sufixo, "aplicada_confirmada")
    email = Email("Gupy <no-reply@gupy.com.br>", "Convite para entrevista", "Ola.")
    recebido = _recebido(sufixo, email)
    resultado = _gravar(
        recebido, Classificacao(Etapa.ENTREVISTA, 1.0, Motivo.RECONHECIDO, "gupy"), vaga_id
    )
    assert resultado.decisao.fila is Etapa.CLASSIFICAR
    assert _estado(banco, vaga_id) == "aplicada_confirmada"
    _, _, aplicado, fila, autenticado, _ = _evento(banco, recebido.id_mensagem)
    assert (aplicado, fila, autenticado) == (False, "classificar", False)


@pytest.mark.parametrize(
    ("tipo", "fila"),
    [("oferta", "suspeito"), ("suspeito", None), ("suspeito", "classificar")],
)
def test_rls_exige_que_fila_suspeito_e_tipo_suspeito_andem_juntos(sufixo, tipo, fila):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _inserir_como_app(f"teste-{sufixo}-par", True, "0.50", fila, tipo)


def test_check_recusa_fila_fora_da_lista(banco, sufixo):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.CheckViolation):
        with banco.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pleito.evento_email (
                    id_mensagem, remetente, autenticado, tipo, confianca, recebido_em, fila
                )
                VALUES (%s, 'x@exemplo.invalid', true, 'oferta', 0.95, now(), 'qualquer')
                """,
                (f"teste-{sufixo}-fila-invalida",),
            )
    banco.rollback()


def test_painel_nao_aplica_evento(banco, sufixo):
    psycopg = pytest.importorskip("psycopg")
    evento_id = _inserir_como_app(f"teste-{sufixo}-painel", True, "0.95", None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with banco.transaction(), banco.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE pleito_painel")
            cursor.execute(
                "UPDATE pleito.evento_email SET aplicado = true WHERE id = %s", (evento_id,)
            )
    assert _evento(banco, f"teste-{sufixo}-painel")[2] is False


def test_rls_recusa_aplicar_evento_nao_autenticado(sufixo):
    psycopg = pytest.importorskip("psycopg")
    evento_id = _inserir_como_app(f"teste-{sufixo}-falso", False, "0.50", None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with conectar("app") as conexao, conexao.cursor() as cursor:
            cursor.execute("UPDATE evento_email SET aplicado = true WHERE id = %s", (evento_id,))


def test_rls_recusa_aplicar_evento_que_esta_na_fila(sufixo):
    evento_id = _inserir_como_app(f"teste-{sufixo}-fila", True, "0.50", "classificar")
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute("UPDATE evento_email SET aplicado = true WHERE id = %s", (evento_id,))
        assert cursor.rowcount == 0


def test_evento_aplicado_nao_pode_estar_numa_fila(banco, sufixo):
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.CheckViolation):
        with banco.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pleito.evento_email (
                    id_mensagem, remetente, autenticado, tipo, confianca, recebido_em,
                    aplicado, fila
                )
                VALUES (%s, 'x@exemplo.invalid', true, 'oferta', 0.95, now(), true, 'classificar')
                """,
                (f"teste-{sufixo}-check",),
            )
    banco.rollback()


AGORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def _empresa(banco, sufixo: str, dominio: str | None) -> tuple[int, str]:
    nome = f"teste-{sufixo}-acme"
    with banco.cursor() as cursor:
        cursor.execute(
            "INSERT INTO pleito.empresa (nome, dominio) VALUES (%s, %s) RETURNING id",
            (nome, dominio),
        )
        empresa_id = cursor.fetchone()[0]
    banco.commit()
    return empresa_id, nome


def _vaga_da_empresa(banco, sufixo: str, estado: str, empresa_id: int) -> int:
    vaga_id = _vaga(banco, sufixo, estado)
    with banco.cursor() as cursor:
        cursor.execute(
            "UPDATE pleito.vaga SET empresa_id = %s WHERE id = %s", (empresa_id, vaga_id)
        )
    banco.commit()
    return vaga_id


def _candidatura(banco, vaga_id: int, plataforma: str) -> None:
    with banco.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO pleito.versao_curriculo (
                vaga_id, familia, idioma, caminho_tex, caminho_pdf, hash_pdf, paginas
            )
            VALUES (%s, 'backend', 'pt', 'x.tex', 'x.pdf', %s, 1)
            RETURNING id
            """,
            (vaga_id, hashlib.sha256(b"pdf").digest()),
        )
        versao_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO pleito.aprovacao (
                vaga_id, versao_id, hash_aprovado, expira_em, consumida_em
            )
            VALUES (%s, %s, %s, now() + interval '1 day', now())
            RETURNING id
            """,
            (vaga_id, versao_id, hashlib.sha256(b"pdf").digest()),
        )
        aprovacao_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO pleito.candidatura (vaga_id, versao_id, aprovacao_id, plataforma)
            VALUES (%s, %s, %s, %s)
            """,
            (vaga_id, versao_id, aprovacao_id, plataforma),
        )
    banco.commit()


def _cfg(tmp_path):
    return configuracao_organizacao(caminho_cursor=tmp_path / "estado" / "cursor.json")


def _rodar(gmail, tmp_path, forcar: bool = True):
    with conectar("app") as conexao:
        return rodada(
            gmail, _cfg(tmp_path), AGORA, forcar=forcar, registro=RegistroNoBanco(conexao)
        )


def _quantos_eventos(banco, sufixo: str) -> int:
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pleito.evento_email WHERE id_mensagem LIKE %s",
            (f"teste-{sufixo}%",),
        )
        return cursor.fetchone()[0]


def _entrevista_da_empresa(sufixo: str, dominio: str, identificador: str = "m1") -> dict:
    return mensagem(
        f"teste-{sufixo}-{identificador}",
        f"RH <rh@{dominio}>",
        "Convite para entrevista",
        "Gostariamos de agendar uma entrevista.",
    )


def _vaga_candidatada(banco, sufixo: str, estado: str) -> tuple[int, str]:
    empresa_id, nome = _empresa(banco, sufixo, None)
    vaga_id = _vaga_da_empresa(banco, sufixo, estado, empresa_id)
    _candidatura(banco, vaga_id, "gupy")
    return vaga_id, nome


def _da_plataforma(sufixo: str, assunto: str, identificador: str = "m1") -> dict:
    return mensagem(f"teste-{sufixo}-{identificador}", "Gupy <no-reply@gupy.com.br>", assunto)


def test_rodada_vincula_pela_plataforma_e_pelo_nome_da_empresa_e_avanca_a_vaga(
    banco, sufixo, tmp_path
):
    vaga_id, nome = _vaga_candidatada(banco, sufixo, "aplicada_confirmada")
    gmail = GmailFalso([_da_plataforma(sufixo, f"Convite para entrevista na {nome}")])
    resumo = _rodar(gmail, tmp_path)
    assert resumo.eventos_gravados == 1
    _, tipo, aplicado, fila, _, vinculada = _evento(banco, f"teste-{sufixo}-m1")
    assert (tipo, aplicado, fila, vinculada) == ("entrevista", True, None, vaga_id)
    assert _estado(banco, vaga_id) == "entrevista"


def test_rodada_vincula_pelo_dominio_da_empresa_mas_remetente_desconhecido_vai_para_classificar(
    banco, sufixo, tmp_path
):
    dominio = f"acme-{sufixo}.exemplo"
    empresa_id, _ = _empresa(banco, sufixo, dominio)
    vaga_id = _vaga_da_empresa(banco, sufixo, "aplicada_confirmada", empresa_id)
    gmail = GmailFalso([_entrevista_da_empresa(sufixo, dominio)])
    _rodar(gmail, tmp_path)
    _, tipo, aplicado, fila, _, vinculada = _evento(banco, f"teste-{sufixo}-m1")
    assert (tipo, aplicado, fila, vinculada) == ("classificar", False, "classificar", vaga_id)
    assert _estado(banco, vaga_id) == "aplicada_confirmada"


def test_rodada_sem_vinculo_deixa_o_evento_sem_vaga_na_fila_classificar(banco, sufixo, tmp_path):
    dominio = f"acme-{sufixo}.exemplo"
    gmail = GmailFalso([_entrevista_da_empresa(sufixo, dominio)])
    _rodar(gmail, tmp_path)
    _, _, aplicado, fila, _, vinculada = _evento(banco, f"teste-{sufixo}-m1")
    assert (aplicado, fila, vinculada) == (False, "classificar", None)


@pytest.mark.parametrize("falso", ["{d}.golpe.exemplo", "mail.{d}", "evil{d}", "{d}-vagas.exemplo"])
def test_rodada_com_dominio_parecido_nao_vincula_nem_muda_a_vaga(banco, sufixo, tmp_path, falso):
    dominio = f"acme-{sufixo}.exemplo"
    empresa_id, _ = _empresa(banco, sufixo, dominio)
    vaga_id = _vaga_da_empresa(banco, sufixo, "aplicada_confirmada", empresa_id)
    gmail = GmailFalso([_entrevista_da_empresa(sufixo, falso.format(d=dominio))])
    _rodar(gmail, tmp_path)
    assert _evento(banco, f"teste-{sufixo}-m1")[5] is None
    assert _estado(banco, vaga_id) == "aplicada_confirmada"


def test_reprocessar_a_mesma_mensagem_nao_duplica_evento_nem_auditoria(banco, sufixo, tmp_path):
    vaga_id, nome = _vaga_candidatada(banco, sufixo, "aplicada_confirmada")
    gmail = GmailFalso([_da_plataforma(sufixo, f"Convite para entrevista na {nome}")])
    primeira = _rodar(gmail, tmp_path)
    gravar_cursor(_cfg(tmp_path).caminho_cursor, Cursor("1", AGORA))
    gmail.paginas = [[f"teste-{sufixo}-m1"]]
    segunda = _rodar(gmail, tmp_path)
    assert (primeira.eventos_gravados, primeira.eventos_repetidos) == (1, 0)
    assert (segunda.eventos_gravados, segunda.eventos_repetidos) == (0, 1)
    assert _quantos_eventos(banco, sufixo) == 1
    evento_id = _evento(banco, f"teste-{sufixo}-m1")[0]
    assert _auditorias(banco, "evento_email", evento_id) == ["registrar_evento", "aplicar_evento"]
    assert _auditorias(banco, "vaga", vaga_id) == ["mudar_estado"]


def test_banco_fora_do_ar_falha_a_rodada_sem_perder_mensagem_e_a_proxima_reprocessa(
    banco, sufixo, tmp_path
):
    dominio = f"acme-{sufixo}.exemplo"
    gmail = GmailFalso(
        [
            _entrevista_da_empresa(sufixo, dominio, "m1"),
            _entrevista_da_empresa(sufixo, dominio, "m2"),
        ]
    )
    conexao = conectar("app")
    conexao.close()
    with pytest.raises(psycopg.OperationalError):
        rodada(gmail, _cfg(tmp_path), AGORA, forcar=True, registro=RegistroNoBanco(conexao))
    assert ler_cursor(_cfg(tmp_path).caminho_cursor) is None
    assert gmail.rotuladas() == {}
    assert _quantos_eventos(banco, sufixo) == 0
    resumo = _rodar(gmail, tmp_path)
    assert resumo.eventos_gravados == 2
    assert _quantos_eventos(banco, sufixo) == 2
    assert ler_cursor(_cfg(tmp_path).caminho_cursor) == Cursor("500", AGORA)


def test_falha_no_meio_desfaz_os_eventos_da_rodada(banco, sufixo, tmp_path, monkeypatch):
    dominio = f"acme-{sufixo}.exemplo"
    gmail = GmailFalso(
        [
            _entrevista_da_empresa(sufixo, dominio, "m1"),
            _entrevista_da_empresa(sufixo, dominio, "m2"),
        ]
    )
    original = RegistroNoBanco.gravar

    def gravar_ou_quebrar(self, recebido, classificacao):
        if recebido.id_mensagem.endswith("m2"):
            raise psycopg.OperationalError("conexao perdida")
        return original(self, recebido, classificacao)

    monkeypatch.setattr(RegistroNoBanco, "gravar", gravar_ou_quebrar)
    with pytest.raises(psycopg.OperationalError):
        _rodar(gmail, tmp_path)
    assert _quantos_eventos(banco, sufixo) == 0
    assert gmail.rotuladas() == {}


def test_rodada_com_aspas_no_remetente_e_no_assunto_grava_literal(banco, sufixo, tmp_path):
    identificador = f"teste-{sufixo}-m1"
    gmail = GmailFalso(
        [
            mensagem(
                identificador,
                f"{ATAQUE} <rh@acme-{sufixo}.exemplo>",
                f"Convite para entrevista {ATAQUE}",
                ATAQUE,
            )
        ]
    )
    _rodar(gmail, tmp_path)
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT remetente FROM pleito.evento_email WHERE id_mensagem = %s", (identificador,)
        )
        assert cursor.fetchone()[0] == f"rh@acme-{sufixo}.exemplo"
        cursor.execute("SELECT to_regclass('pleito.evento_email') IS NOT NULL")
        assert cursor.fetchone()[0] is True
