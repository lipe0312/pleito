from __future__ import annotations

import base64
import copy
import hashlib
import http.client
import json
import threading
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
import respx

from src.config import carregar
from src.email.configuracao import EscopoProibido, configuracao_gmail
from src.email.oauth import (
    AutorizacaoNegada,
    ClienteInvalido,
    ClienteOAuth,
    ServidorLoopback,
    StateInvalido,
    autorizar,
    gerar_pkce,
    ler_cliente,
    montar_url_autorizacao,
    renovar,
    trocar_codigo,
    validar_callback,
)

CLIENTE = ClienteOAuth("id-ficticio.apps.exemplo", "segredo-ficticio")
REDIRECT = "http://127.0.0.1:5555/"


@pytest.fixture
def cfg():
    return configuracao_gmail(copy.deepcopy(carregar("emails")))


class ChaveFalsa:
    def __init__(self) -> None:
        self.gravados: list[str] = []

    def gravar(self, valor: str) -> None:
        self.gravados.append(valor)


class ServidorFalso:
    def __init__(self, resposta) -> None:
        self.resposta = resposta
        self.redirect_uri = REDIRECT
        self.url_aberta = ""

    def __call__(self, *_args):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def esperar(self, _segundos: float, _state: str) -> str:
        state = parse_qs(urlsplit(self.url_aberta).query)["state"][0]
        return self.resposta(state)

    def abrir(self, url: str) -> None:
        self.url_aberta = url


def test_pkce_usa_s256_sobre_o_verifier():
    verifier, challenge = gerar_pkce()
    assert 43 <= len(verifier) <= 128
    esperado = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert challenge == esperado.rstrip(b"=").decode()


def test_url_de_autorizacao_pede_so_os_escopos_do_config_com_pkce(cfg):
    url = montar_url_autorizacao(cfg, CLIENTE.client_id, REDIRECT, "estado", "desafio")
    partes = urlsplit(url)
    parametros = parse_qs(partes.query)
    assert f"{partes.scheme}://{partes.netloc}{partes.path}" == cfg.url_autorizacao
    assert parametros["scope"] == [" ".join(cfg.escopos)]
    assert parametros["code_challenge_method"] == ["S256"]
    assert parametros["code_challenge"] == ["desafio"]
    assert parametros["state"] == ["estado"]
    assert parametros["redirect_uri"] == [REDIRECT]
    assert parametros["access_type"] == ["offline"]
    assert "include_granted_scopes" not in parametros


def test_cliente_desktop_e_lido_do_json(tmp_path):
    caminho = tmp_path / "cliente.json"
    caminho.write_text(json.dumps({"installed": {"client_id": "a", "client_secret": "b"}}))
    assert ler_cliente(caminho) == ClienteOAuth("a", "b")


def test_cliente_que_nao_e_desktop_e_recusado(tmp_path):
    caminho = tmp_path / "cliente.json"
    caminho.write_text(json.dumps({"web": {"client_id": "a", "client_secret": "b"}}))
    with pytest.raises(ClienteInvalido):
        ler_cliente(caminho)


def test_callback_com_state_correto_devolve_o_codigo():
    assert validar_callback(urlencode({"code": "c1", "state": "s1"}), "s1") == "c1"


@pytest.mark.parametrize(
    "consulta",
    [
        urlencode({"code": "c1", "state": "forjado"}),
        urlencode({"code": "c1"}),
        urlencode([("code", "c1"), ("state", "s1"), ("state", "forjado")]),
        urlencode({"code": "c1", "state": ""}),
    ],
)
def test_state_forjado_ou_ausente_no_callback_e_recusado(consulta):
    with pytest.raises(StateInvalido):
        validar_callback(consulta, "s1")


def test_erro_no_callback_vira_autorizacao_negada():
    with pytest.raises(AutorizacaoNegada):
        validar_callback(urlencode({"error": "access_denied", "state": "s1"}), "s1")


@respx.mock
def test_troca_do_codigo_manda_o_verifier(cfg):
    rota = respx.post(cfg.url_token).mock(
        return_value=httpx.Response(200, json={"access_token": "a", "refresh_token": "r"})
    )
    with httpx.Client() as http:
        tokens = trocar_codigo(cfg, CLIENTE, "codigo", "verificador", REDIRECT, http)
    corpo = parse_qs(rota.calls.last.request.content.decode())
    assert corpo["grant_type"] == ["authorization_code"]
    assert corpo["code_verifier"] == ["verificador"]
    assert corpo["redirect_uri"] == [REDIRECT]
    assert tokens == {"access_token": "a", "refresh_token": "r"}


@respx.mock
def test_renovacao_usa_o_refresh_token(cfg):
    rota = respx.post(cfg.url_token).mock(
        return_value=httpx.Response(200, json={"access_token": "novo"})
    )
    with httpx.Client() as http:
        tokens = renovar(cfg, CLIENTE, "refresh-ficticio", http)
    corpo = parse_qs(rota.calls.last.request.content.decode())
    assert corpo["grant_type"] == ["refresh_token"]
    assert corpo["refresh_token"] == ["refresh-ficticio"]
    assert tokens == {"access_token": "novo"}


def _autorizar(cfg, servidor, chave, http):
    autorizar(
        cfg,
        chave,
        http,
        cliente=CLIENTE,
        abrir_navegador=servidor.abrir,
        criar_servidor=servidor,
    )


@respx.mock
def test_fluxo_completo_grava_so_o_refresh_token(cfg):
    escopo = " ".join(cfg.escopos)
    rota = respx.post(cfg.url_token).mock(
        return_value=httpx.Response(
            200, json={"access_token": "a", "refresh_token": "r-ficticio", "scope": escopo}
        )
    )
    servidor = ServidorFalso(lambda state: urlencode({"code": "c", "state": state}))
    chave = ChaveFalsa()
    with httpx.Client() as http:
        _autorizar(cfg, servidor, chave, http)
    assert chave.gravados == ["r-ficticio"]
    assert rota.call_count == 1


@respx.mock
def test_state_forjado_no_fluxo_nao_troca_codigo_nem_grava(cfg):
    rota = respx.post(cfg.url_token).mock(return_value=httpx.Response(200, json={}))
    servidor = ServidorFalso(lambda _state: urlencode({"code": "c", "state": "forjado"}))
    chave = ChaveFalsa()
    with httpx.Client() as http, pytest.raises(StateInvalido):
        _autorizar(cfg, servidor, chave, http)
    assert rota.call_count == 0
    assert chave.gravados == []


@respx.mock
def test_escopo_concedido_alem_da_allowlist_nao_e_gravado(cfg):
    respx.post(cfg.url_token).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "a",
                "refresh_token": "r",
                "scope": "https://www.googleapis.com/auth/gmail.modify https://mail.google.com/",
            },
        )
    )
    servidor = ServidorFalso(lambda state: urlencode({"code": "c", "state": state}))
    chave = ChaveFalsa()
    with httpx.Client() as http, pytest.raises(EscopoProibido):
        _autorizar(cfg, servidor, chave, http)
    assert chave.gravados == []


def test_servidor_loopback_recebe_um_callback_local():
    with ServidorLoopback("127.0.0.1", 0, "ok") as servidor:
        assert servidor.redirect_uri.startswith("http://127.0.0.1:")
        partes = urlsplit(servidor.redirect_uri)
        caminho = "/?" + urlencode({"code": "c", "state": "s"})

        def chamar() -> None:
            conexao = http.client.HTTPConnection(partes.hostname, partes.port, timeout=5)
            conexao.request("GET", caminho)
            conexao.getresponse().read()
            conexao.close()

        linha = threading.Thread(target=chamar)
        linha.start()
        consulta = servidor.esperar(5, "s")
        linha.join()
    assert parse_qs(consulta) == {"code": ["c"], "state": ["s"]}


def test_callback_forjado_antes_do_real_e_ignorado_pelo_servidor():
    with ServidorLoopback("127.0.0.1", 0, "ok") as servidor:
        partes = urlsplit(servidor.redirect_uri)
        status: list[int] = []

        def chamar() -> None:
            for consulta in (
                {"code": "forjado", "state": "forjado"},
                {"error": "access_denied", "state": "forjado"},
                {"code": "real", "state": "s"},
            ):
                conexao = http.client.HTTPConnection(partes.hostname, partes.port, timeout=5)
                conexao.request("GET", "/?" + urlencode(consulta))
                resposta = conexao.getresponse()
                resposta.read()
                status.append(resposta.status)
                conexao.close()

        linha = threading.Thread(target=chamar)
        linha.start()
        consulta = servidor.esperar(5, "s")
        linha.join()
    assert parse_qs(consulta) == {"code": ["real"], "state": ["s"]}
    assert status == [400, 400, 200]


def test_servidor_sem_callback_valido_estoura_o_tempo():
    with ServidorLoopback("127.0.0.1", 0, "ok") as servidor, pytest.raises(TimeoutError):
        servidor.esperar(0.2, "s")
