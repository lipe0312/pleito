from __future__ import annotations

from datetime import UTC, datetime

from src.email.cursor import Cursor, gravar_cursor
from src.email.organizador import configuracao_organizacao, rodada
from tests.apoio_alertas import casos
from tests.test_email_organizador import GmailFalso

AGORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
NOMES_DE_ALERTA = (
    "alerta_com_tres_vagas",
    "recomendacao_de_vagas",
    "alerta_sem_vaga_nova",
    "candidatura_vista",
    "convite_de_conexao",
    "mensagem_de_recrutador_com_link_de_vaga",
    "post_com_link_de_vaga",
    "newsletter",
    "aviso_de_login",
    "premium_em_caixa_de_alerta",
    "caixa_desconhecida_do_dominio_exato",
    "cartao_sem_empresa_junto_de_cartao_completo",
)


def _rodar(tmp_path, nomes):
    mensagens = [c.mensagem(f"m{i}") for i, c in enumerate(casos()) if c.nome in nomes]
    gmail = GmailFalso(mensagens, historico=[[m["id"] for m in mensagens]])
    cfg = configuracao_organizacao(caminho_cursor=tmp_path / "c.json")
    gravar_cursor(cfg.caminho_cursor, Cursor("700", AGORA - cfg.intervalo))
    rodada(gmail, cfg, AGORA)
    return gmail


def test_organizador_nao_rotula_nem_arquiva_email_de_alerta_do_linkedin(tmp_path):
    gmail = _rodar(tmp_path, NOMES_DE_ALERTA)
    assert gmail.rotuladas() == {}
    assert gmail.arquivadas() == []


def test_organizador_continua_rotulando_retorno_e_golpe_do_linkedin(tmp_path):
    gmail = _rodar(
        tmp_path,
        ("retorno_de_candidatura", "remetente_linkedin_com_golpe_net", "dmarc_fail"),
    )
    assert len(gmail.rotuladas()) == 3
    assert len(gmail.arquivadas()) == 3
