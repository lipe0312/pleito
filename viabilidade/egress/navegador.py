from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlparse

from viabilidade.config import ambiente
from viabilidade.conformidade import dominios_permitidos, host_permitido

CAMPOS_PROIBIDOS = ("password", "senha", "cpf", "credit", "cartao")

TIPOS_ESTATICOS = frozenset(
    {"script", "stylesheet", "font", "image", "media", "manifest", "texttrack", "other"}
)
TIPOS_NAVEGACAO = frozenset({"document", "xhr", "fetch", "websocket"})


class SubmitBloqueado(Exception):
    pass


class CampoProibido(Exception):
    pass


def exigir_campo_seguro(seletor: str) -> None:
    baixo = seletor.lower()
    for proibido in CAMPOS_PROIBIDOS:
        if proibido in baixo:
            raise CampoProibido(f"seletor {seletor!r} toca dado que o sistema nunca preenche")


def exigir_submit_autorizado() -> None:
    env = ambiente()
    if not env.submit_real_autorizado:
        raise SubmitBloqueado(
            "submit real exige PLEITO_EGRESS_MODO=submit_real e token de autorizacao com 16+ chars"
        )


@contextmanager
def navegador_persistente(rota_bloqueada: bool = True) -> Iterator:
    from playwright.sync_api import sync_playwright

    env = ambiente()
    env.egress_perfil.mkdir(parents=True, exist_ok=True)
    permitidos = dominios_permitidos()

    with sync_playwright() as p:
        contexto = p.chromium.launch_persistent_context(
            user_data_dir=str(env.egress_perfil),
            headless=False,
            accept_downloads=False,
            user_agent=env.user_agent,
        )
        if rota_bloqueada:
            bloqueados: list[str] = []

            def filtrar(rota):
                pedido = rota.request
                host = urlparse(pedido.url).netloc.lower().split(":")[0]
                if not host or host_permitido(host, permitidos):
                    rota.continue_()
                    return
                if pedido.resource_type in TIPOS_ESTATICOS:
                    rota.continue_()
                    return
                bloqueados.append(f"{pedido.resource_type} {host}")
                rota.abort()

            contexto.route("**/*", filtrar)
            contexto.pleito_bloqueados = bloqueados
        try:
            yield contexto
        finally:
            contexto.close()
