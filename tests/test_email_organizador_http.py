from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from src.config import carregar
from src.email.configuracao import configuracao_gmail
from src.email.cursor import Cursor, gravar_cursor
from src.email.gmail import ClienteGmail, IdentificadorInvalido
from src.email.oauth import ClienteOAuth
from src.email.organizador import configuracao_organizacao, rodada
from tests.test_email_gmail import ChaveFalsa
from tests.test_email_organizador import GUPY, _rotulos_da_conta, mensagem

AGORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
CLIENTE = ClienteOAuth("id-ficticio.apps.exemplo", "segredo-ficticio")


@pytest.fixture
def cfg():
    return configuracao_gmail(copy.deepcopy(carregar("emails")))


def _cliente(cfg) -> ClienteGmail:
    return ClienteGmail(cfg, ChaveFalsa(), httpx.Client(), CLIENTE)


def _montar_gmail(cfg, mensagens: list[dict]) -> None:
    respx.post(cfg.url_token).mock(return_value=httpx.Response(200, json={"access_token": "a"}))
    respx.get(f"{cfg.url_api}/labels").mock(
        return_value=httpx.Response(200, json={"labels": _rotulos_da_conta()})
    )
    respx.get(f"{cfg.url_api}/history").mock(
        return_value=httpx.Response(
            200,
            json={
                "historyId": "901",
                "history": [{"messagesAdded": [{"message": {"id": m["id"]}} for m in mensagens]}],
            },
        )
    )
    for item in mensagens:
        respx.get(f"{cfg.url_api}/messages/{item['id']}").mock(
            return_value=httpx.Response(200, json=item)
        )
        respx.post(f"{cfg.url_api}/messages/{item['id']}/modify").mock(
            return_value=httpx.Response(200, json={})
        )


@respx.mock
def test_rodada_real_so_faz_get_e_modify_sem_tirar_rotulo_de_sistema(cfg, tmp_path):
    organizacao = configuracao_organizacao(caminho_cursor=tmp_path / "c.json")
    gravar_cursor(organizacao.caminho_cursor, Cursor("700", AGORA - organizacao.intervalo))
    _montar_gmail(
        cfg,
        [
            mensagem("m1", GUPY, "Convite para entrevista"),
            mensagem("m2", "Vagas <rh@gupy-vagas.com>", "Ola"),
            mensagem("m3", GUPY, "Proposta de emprego", autenticacao="mx; dmarc=fail"),
        ],
    )
    rodada(_cliente(cfg), organizacao, AGORA)
    pedidos = [chamada.request for chamada in respx.calls]
    api = [p for p in pedidos if str(p.url).startswith(cfg.url_api)]
    assert {p.method for p in api} == {"GET", "POST"}
    escritas = [p for p in api if p.method == "POST"]
    assert escritas and all(p.url.path.endswith("/modify") for p in escritas)
    removidos = {
        rotulo for p in escritas for rotulo in json.loads(p.content)["removeLabelIds"]
    }
    assert removidos == {cfg.rotulo_caixa_entrada}
    adicionados = {
        rotulo for p in escritas for rotulo in json.loads(p.content)["addLabelIds"]
    }
    assert adicionados and all(rotulo.startswith("Label_") for rotulo in adicionados)


@respx.mock
def test_historico_pede_so_mensagens_novas_da_caixa(cfg):
    respx.post(cfg.url_token).mock(return_value=httpx.Response(200, json={"access_token": "a"}))
    rota = respx.get(f"{cfg.url_api}/history").mock(
        return_value=httpx.Response(200, json={"historyId": "9"})
    )
    _cliente(cfg).historico("7", cfg.rotulo_caixa_entrada, "pagina-2")
    parametros = rota.calls.last.request.url.params
    assert parametros["startHistoryId"] == "7"
    assert parametros["historyTypes"] == "messageAdded"
    assert parametros["labelId"] == cfg.rotulo_caixa_entrada
    assert parametros["pageToken"] == "pagina-2"


@respx.mock
@pytest.mark.parametrize("inicio", ["", "12a", "1&labelId=TRASH", "../1"])
def test_history_id_invalido_e_recusado_sem_chamar_a_api(cfg, inicio):
    with pytest.raises(IdentificadorInvalido):
        _cliente(cfg).historico(inicio, cfg.rotulo_caixa_entrada)
    assert not respx.calls
