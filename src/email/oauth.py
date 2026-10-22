from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from src.email.configuracao import ConfiguracaoGmail, exigir_escopos_permitidos


class ClienteInvalido(ValueError):
    pass


class StateInvalido(ValueError):
    pass


class AutorizacaoNegada(RuntimeError):
    pass


class RefreshTokenAusente(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ClienteOAuth:
    client_id: str
    client_secret: str


def ler_cliente(caminho: Path) -> ClienteOAuth:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    instalado = dados.get("installed")
    if not isinstance(instalado, dict):
        raise ClienteInvalido("o cliente OAuth precisa ser do tipo Desktop")
    try:
        return ClienteOAuth(instalado["client_id"], instalado["client_secret"])
    except KeyError as erro:
        raise ClienteInvalido("cliente OAuth incompleto") from erro


def gerar_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    resumo = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(resumo).rstrip(b"=").decode("ascii")
    return verifier, challenge


def montar_url_autorizacao(
    cfg: ConfiguracaoGmail, client_id: str, redirect_uri: str, state: str, challenge: str
) -> str:
    parametros = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(cfg.escopos),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{cfg.url_autorizacao}?{urlencode(parametros)}"


def validar_callback(consulta: str, state_esperado: str) -> str:
    parametros = parse_qs(consulta, keep_blank_values=True)
    states = parametros.get("state", [])
    if len(states) != 1 or not states[0]:
        raise StateInvalido("state ausente ou repetido")
    if not hmac.compare_digest(states[0].encode(), state_esperado.encode()):
        raise StateInvalido("state nao confere")
    if "error" in parametros:
        raise AutorizacaoNegada(parametros["error"][0])
    codigos = parametros.get("code", [])
    if len(codigos) != 1 or not codigos[0]:
        raise AutorizacaoNegada("callback sem codigo")
    return codigos[0]


def _pedir_token(cfg: ConfiguracaoGmail, http: httpx.Client, corpo: dict[str, str]) -> dict:
    resposta = http.post(cfg.url_token, data=corpo, timeout=cfg.timeout_s)
    resposta.raise_for_status()
    return resposta.json()


def trocar_codigo(
    cfg: ConfiguracaoGmail,
    cliente: ClienteOAuth,
    codigo: str,
    verifier: str,
    redirect_uri: str,
    http: httpx.Client,
) -> dict:
    return _pedir_token(
        cfg,
        http,
        {
            "grant_type": "authorization_code",
            "code": codigo,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "client_id": cliente.client_id,
            "client_secret": cliente.client_secret,
        },
    )


def renovar(
    cfg: ConfiguracaoGmail, cliente: ClienteOAuth, refresh_token: str, http: httpx.Client
) -> dict:
    return _pedir_token(
        cfg,
        http,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": cliente.client_id,
            "client_secret": cliente.client_secret,
        },
    )


class ServidorLoopback:
    def __init__(self, host: str, porta: int, mensagem: str) -> None:
        recebidas: list[str] = []
        corpo = mensagem.encode("utf-8")

        class Receptor(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                consulta = urlsplit(self.path).query
                parametros = parse_qs(consulta)
                if "state" in parametros or "error" in parametros:
                    recebidas.append(consulta)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *_args) -> None:
                return

        self._recebidas = recebidas
        self._servidor = HTTPServer((host, porta), Receptor)
        endereco, porta_real = self._servidor.server_address[:2]
        self.redirect_uri = f"http://{endereco}:{porta_real}/"

    def __enter__(self) -> ServidorLoopback:
        return self

    def __exit__(self, *_exc) -> bool:
        self._servidor.server_close()
        return False

    def esperar(self, segundos: float) -> str:
        limite = time.monotonic() + segundos
        while not self._recebidas:
            restante = limite - time.monotonic()
            if restante <= 0:
                raise TimeoutError("callback do OAuth nao chegou")
            self._servidor.timeout = restante
            self._servidor.handle_request()
        return self._recebidas[0]


def autorizar(
    cfg: ConfiguracaoGmail,
    chave,
    http: httpx.Client,
    cliente: ClienteOAuth | None = None,
    abrir_navegador: Callable[[str], object] = webbrowser.open,
    criar_servidor: Callable[[str, int, str], ServidorLoopback] = ServidorLoopback,
) -> None:
    cliente = cliente or ler_cliente(cfg.caminho_cliente)
    verifier, challenge = gerar_pkce()
    state = secrets.token_urlsafe(32)
    with criar_servidor(cfg.loopback_host, cfg.loopback_porta, cfg.mensagem_callback) as servidor:
        redirect_uri = servidor.redirect_uri
        abrir_navegador(
            montar_url_autorizacao(cfg, cliente.client_id, redirect_uri, state, challenge)
        )
        consulta = servidor.esperar(cfg.espera_callback_s)
    codigo = validar_callback(consulta, state)
    tokens = trocar_codigo(cfg, cliente, codigo, verifier, redirect_uri, http)
    concedidos = tokens.get("scope", "").split()
    exigir_escopos_permitidos(concedidos or list(cfg.escopos))
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RefreshTokenAusente("o Google nao devolveu refresh_token")
    chave.gravar(refresh_token)
