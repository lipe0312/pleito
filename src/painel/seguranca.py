from __future__ import annotations

import secrets

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config import carregar


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


class ProtecaoPainel:
    def __init__(self, app: ASGIApp, token: str) -> None:
        configuracao = carregar("painel")
        porta = configuracao["porta"]
        hosts = [str(host).lower() for host in configuracao["hosts_permitidos"]]
        self.app = app
        self.token = token.encode("utf-8")
        self.hosts = {f"{host}:{porta}" for host in hosts}
        self.origens = {f"http://{host}:{porta}" for host in hosts}
        self.cabecalho_csrf = configuracao["csrf_cabecalho"]
        self.metodos_seguros = {str(m).upper() for m in configuracao["metodos_seguros"]}
        self.cabecalhos = {
            **{str(k): str(v) for k, v in configuracao["cabecalhos"].items()},
            "Content-Security-Policy": "; ".join(
                f"{diretiva} {fontes}" for diretiva, fontes in configuracao["csp"].items()
            ),
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def enviar(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                cabecalhos = MutableHeaders(scope=mensagem)
                for nome, valor in self.cabecalhos.items():
                    cabecalhos[nome] = valor
            await send(mensagem)

        recusa = self.recusar(scope)
        if recusa is not None:
            await recusa(scope, receive, enviar)
            return
        await self.app(scope, receive, enviar)

    def recusar(self, scope: Scope) -> PlainTextResponse | None:
        cabecalhos = Headers(scope=scope)
        hosts = cabecalhos.getlist("host")
        if len(hosts) != 1 or hosts[0].lower() not in self.hosts:
            return PlainTextResponse("host nao permitido", status_code=400)
        if scope["method"].upper() in self.metodos_seguros:
            return None
        origem = cabecalhos.get("origin")
        if origem is not None and origem.lower() not in self.origens:
            return PlainTextResponse("origem nao permitida", status_code=403)
        if cabecalhos.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            return PlainTextResponse("origem nao permitida", status_code=403)
        enviado = cabecalhos.get(self.cabecalho_csrf, "").encode("utf-8")
        if not secrets.compare_digest(enviado, self.token):
            return PlainTextResponse("token csrf invalido", status_code=403)
        return None
