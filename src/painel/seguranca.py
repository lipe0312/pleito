from __future__ import annotations

import secrets

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config import carregar


def gerar_token(tamanho: int) -> str:
    return secrets.token_urlsafe(tamanho)


class ProtecaoPainel:
    def __init__(self, app: ASGIApp, token: str) -> None:
        configuracao = carregar("painel")
        porta = configuracao["porta"]
        hosts = [str(host).lower() for host in configuracao["hosts_permitidos"]]
        self.app = app
        self.token = token.encode("utf-8")
        self.hosts = {f"{host}:{porta}" for host in hosts}
        self.origens = {f"{configuracao['esquema_origem']}://{host}:{porta}" for host in hosts}
        self.fetch_site_aceitos = set(configuracao["fetch_site_aceitos"])
        self.cabecalho_csrf = configuracao["csrf_cabecalho"]
        self.metodos_seguros = {str(m).upper() for m in configuracao["metodos_seguros"]}
        self.cabecalhos = {
            **{str(k): str(v) for k, v in configuracao["cabecalhos"].items()},
            "Content-Security-Policy": "; ".join(
                f"{diretiva} {fontes}" for diretiva, fontes in configuracao["csp"].items()
            ),
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
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
        fetch_site = cabecalhos.get("sec-fetch-site")
        if fetch_site is not None and fetch_site not in self.fetch_site_aceitos:
            return PlainTextResponse("origem nao permitida", status_code=403)
        enviado = cabecalhos.get(self.cabecalho_csrf, "").encode("utf-8")
        if not secrets.compare_digest(enviado, self.token):
            return PlainTextResponse("token csrf invalido", status_code=403)
        return None
