from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from src.email.cursor import Cursor, gravar_cursor, ler_cursor
from src.email.mensagem import recebido_em_de
from src.email.modelo import Classificacao, Etapa
from src.email.organizador import configuracao_organizacao, rodada
from src.email.repositorio import EmailRecebido, ResultadoEvento
from tests.test_email_organizador import AGORA, GUPY, GmailFalso, mensagem

ANTES = AGORA.replace(hour=11)


class RegistroFalso:
    def __init__(self) -> None:
        self.eventos: dict[str, tuple[EmailRecebido, Classificacao]] = {}
        self.chamadas: list[str] = []
        self.falhar_ao_gravar: str | None = None
        self.falhar_ao_confirmar = False
        self.pendentes: dict[str, tuple[EmailRecebido, Classificacao]] = {}

    def gravar(self, recebido: EmailRecebido, classificacao: Classificacao) -> ResultadoEvento:
        self.chamadas.append(f"gravar:{recebido.id_mensagem}")
        if recebido.id_mensagem == self.falhar_ao_gravar:
            raise ConnectionError("banco fora do ar")
        if recebido.id_mensagem in self.eventos or recebido.id_mensagem in self.pendentes:
            return ResultadoEvento(None, True)
        self.pendentes[recebido.id_mensagem] = (recebido, classificacao)
        return ResultadoEvento(len(self.eventos) + len(self.pendentes), False)

    def confirmar(self) -> None:
        self.chamadas.append("confirmar")
        if self.falhar_ao_confirmar:
            raise ConnectionError("banco fora do ar")
        self.eventos.update(self.pendentes)
        self.pendentes = {}

    def desfazer(self) -> None:
        self.chamadas.append("desfazer")
        self.pendentes = {}


@pytest.fixture
def cfg(tmp_path: Path):
    return configuracao_organizacao(caminho_cursor=tmp_path / "estado" / "cursor.json")


def _preparar(cfg, mensagens: list[dict], paginas: list[list[str]]):
    gravar_cursor(cfg.caminho_cursor, Cursor("700", ANTES - cfg.intervalo))
    return GmailFalso(mensagens, historico=paginas)


def _entrevista(identificador: str = "m1") -> dict:
    return mensagem(identificador, GUPY, "Convite para entrevista")


def test_mensagem_relevante_vira_evento_com_id_da_mensagem_e_classificacao(cfg):
    gmail = _preparar(cfg, [_entrevista()], [["m1"]])
    registro = RegistroFalso()
    resumo = rodada(gmail, cfg, AGORA, registro=registro)
    recebido, classificacao = registro.eventos["m1"]
    assert recebido.id_mensagem == "m1"
    assert recebido.email.assunto == "Convite para entrevista"
    assert classificacao.etapa is Etapa.ENTREVISTA
    assert resumo.eventos_gravados == 1


def test_mensagem_irrelevante_e_a_pessoal_nao_viram_evento(cfg):
    gmail = _preparar(
        cfg,
        [
            mensagem("m1", "Amiga <amiga@exemplo.org>", "Almoco", autenticacao=""),
            mensagem("m2", "Vagas <rh@gupy-vagas.exemplo>", "Ola"),
        ],
        [["m1", "m2"]],
    )
    registro = RegistroFalso()
    rodada(gmail, cfg, AGORA, registro=registro)
    assert "gravar:m1" not in registro.chamadas
    assert registro.eventos.keys() == {"m2"}


def test_golpe_vira_evento_suspeito_para_a_fila(cfg):
    gmail = _preparar(
        cfg, [mensagem("m1", "Gupy <rh@gupy-vagas.exemplo>", "Convite para entrevista")], [["m1"]]
    )
    registro = RegistroFalso()
    rodada(gmail, cfg, AGORA, registro=registro)
    assert registro.eventos["m1"][1].etapa is Etapa.SUSPEITO


def test_horario_do_evento_vem_do_internal_date_ou_da_rodada(cfg):
    com_data = _entrevista("m1") | {"internalDate": "1760000000000"}
    gmail = _preparar(cfg, [com_data, _entrevista("m2")], [["m1", "m2"]])
    registro = RegistroFalso()
    rodada(gmail, cfg, AGORA, registro=registro)
    assert registro.eventos["m1"][0].recebido_em == datetime(2025, 10, 9, 8, 53, 20, tzinfo=UTC)
    assert registro.eventos["m2"][0].recebido_em == AGORA


@pytest.mark.parametrize("valor", ["", "abc", "-5", "9" * 40, None, 12])
def test_internal_date_invalido_cai_no_horario_da_rodada(valor):
    assert recebido_em_de({"internalDate": valor}, AGORA) == AGORA


def test_eventos_sao_gravados_e_confirmados_antes_de_mexer_no_gmail(cfg):
    gmail = _preparar(cfg, [_entrevista("m1"), _entrevista("m2")], [["m1", "m2"]])
    registro = RegistroFalso()
    gmail.rotular = lambda *a: registro.chamadas.append("rotular") or {}
    rodada(gmail, cfg, AGORA, registro=registro)
    assert registro.chamadas == ["gravar:m1", "gravar:m2", "confirmar", "rotular", "rotular"]


def test_banco_fora_do_ar_ao_gravar_falha_sem_mexer_no_gmail_nem_no_cursor(cfg):
    gmail = _preparar(cfg, [_entrevista("m1"), _entrevista("m2")], [["m1", "m2"]])
    registro = RegistroFalso()
    registro.falhar_ao_gravar = "m2"
    with pytest.raises(ConnectionError):
        rodada(gmail, cfg, AGORA, registro=registro)
    assert gmail.rotuladas() == {}
    assert gmail.arquivadas() == []
    assert registro.eventos == {}
    assert registro.chamadas[-1] == "desfazer"
    assert ler_cursor(cfg.caminho_cursor) == Cursor("700", ANTES - cfg.intervalo)


def test_banco_fora_do_ar_ao_confirmar_nao_avanca_cursor_nem_rotula(cfg):
    gmail = _preparar(cfg, [_entrevista()], [["m1"]])
    registro = RegistroFalso()
    registro.falhar_ao_confirmar = True
    with pytest.raises(ConnectionError):
        rodada(gmail, cfg, AGORA, registro=registro)
    assert gmail.rotuladas() == {}
    assert ler_cursor(cfg.caminho_cursor) == Cursor("700", ANTES - cfg.intervalo)


def test_proxima_rodada_apos_banco_fora_do_ar_grava_tudo_uma_vez(cfg):
    gmail = _preparar(cfg, [_entrevista("m1"), _entrevista("m2")], [["m1", "m2"]])
    registro = RegistroFalso()
    registro.falhar_ao_gravar = "m2"
    with pytest.raises(ConnectionError):
        rodada(gmail, cfg, AGORA, registro=registro)
    registro.falhar_ao_gravar = None
    resumo = rodada(gmail, cfg, AGORA, registro=registro)
    assert registro.eventos.keys() == {"m1", "m2"}
    assert resumo.eventos_gravados == 2
    assert resumo.eventos_repetidos == 0
    assert ler_cursor(cfg.caminho_cursor) == Cursor("900", AGORA)


def test_falha_no_gmail_depois_dos_eventos_nao_avanca_cursor_e_reprocessa_sem_duplicar(cfg):
    gmail = _preparar(cfg, [_entrevista("m1"), _entrevista("m2")], [["m1", "m2"]])
    registro = RegistroFalso()
    original = gmail.arquivar

    def quebrar_no_segundo(identificador):
        if identificador == "m2":
            raise httpx.ConnectError("sem rede")
        return original(identificador)

    gmail.arquivar = quebrar_no_segundo
    with pytest.raises(httpx.ConnectError):
        rodada(gmail, cfg, AGORA, registro=registro)
    assert registro.eventos.keys() == {"m1", "m2"}
    assert ler_cursor(cfg.caminho_cursor) == Cursor("700", ANTES - cfg.intervalo)

    gmail.arquivar = original
    gmail.mensagens["m1"]["labelIds"] = ["UNREAD"]
    resumo = rodada(gmail, cfg, AGORA, registro=registro)
    assert len(registro.eventos) == 2
    assert resumo.eventos_repetidos == 1
    assert resumo.eventos_gravados == 0
    assert resumo.fora_da_caixa == 1
    assert ler_cursor(cfg.caminho_cursor) == Cursor("900", AGORA)


def test_mensagem_ja_vista_conta_como_repetida_e_ainda_e_rotulada(cfg):
    gmail = _preparar(cfg, [_entrevista()], [["m1"]])
    registro = RegistroFalso()
    rodada(gmail, cfg, AGORA, registro=registro)
    gravar_cursor(cfg.caminho_cursor, Cursor("700", ANTES - cfg.intervalo))
    resumo = rodada(gmail, cfg, AGORA, registro=registro)
    assert resumo.eventos_repetidos == 1
    assert len(registro.eventos) == 1
    assert len(gmail.rotuladas()) == 1


def test_rodada_adiada_nao_toca_no_registro(cfg):
    gravar_cursor(cfg.caminho_cursor, Cursor("700", AGORA))
    registro = RegistroFalso()
    resumo = rodada(GmailFalso([]), cfg, AGORA, registro=registro)
    assert resumo.adiada
    assert registro.chamadas == []


def test_rodada_sem_novas_confirma_vazio_e_avanca_o_cursor(cfg):
    gmail = _preparar(cfg, [], [[]])
    registro = RegistroFalso()
    rodada(gmail, cfg, AGORA, registro=registro)
    assert registro.chamadas == ["confirmar"]
    assert ler_cursor(cfg.caminho_cursor) == Cursor("900", AGORA)
