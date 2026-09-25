from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlparse

from viabilidade.config import ambiente
from viabilidade.conformidade import dominios_permitidos

CAMPOS_PROIBIDOS = ("password", "senha", "cpf", "credit", "cartao")


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

            def filtrar(rota):
                host = urlparse(rota.request.url).netloc.lower().split(":")[0]
                if host and not any(host.endswith(d) for d in permitidos):
                    rota.abort()
                else:
                    rota.continue_()

            contexto.route("**/*", filtrar)
        try:
            yield contexto
        finally:
            contexto.close()
