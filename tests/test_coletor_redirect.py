from __future__ import annotations

import httpx
import pytest
import respx

from src.coletor.base import ColetorHttp
from src.coletor.conformidade import DominioNaoPermitido, Limitador
from src.config import carregar

ORIGEM = "https://boards-api.greenhouse.io/v1/boards/x/jobs"
DESTINO_PERMITIDO = "https://job-boards.greenhouse.io/x/jobs"
DESTINO_EXTERNO = "https://servidor-externo.example.net/vagas"
ROBOTS_PERMITE = "User-agent: *\nAllow: /\n"
ROBOTS_BLOQUEIA = "User-agent: *\nDisallow: /\n"


@pytest.fixture
def coletor():
    cliente = httpx.Client(follow_redirects=True)
    c = ColetorHttp(client=cliente)
    c._limitador = Limitador(0)
    yield c
    cliente.close()


def _redireciona(para: str) -> httpx.Response:
    return httpx.Response(302, headers={"Location": para})


@respx.mock
def test_redirect_para_host_fora_da_allowlist_e_bloqueado_sem_requisitar_o_destino(coletor):
    respx.get(ORIGEM).mock(return_value=_redireciona(DESTINO_EXTERNO))
    destino = respx.get(DESTINO_EXTERNO).mock(return_value=httpx.Response(200, text="x"))
    with pytest.raises(DominioNaoPermitido):
        coletor._buscar(ORIGEM)
    assert not destino.called


@respx.mock
def test_redirect_para_host_que_imita_dominio_permitido_e_bloqueado(coletor):
    imitado = "https://boards-api.greenhouse.io.evil.com/v1/boards/x/jobs"
    respx.get(ORIGEM).mock(return_value=_redireciona(imitado))
    destino = respx.get(imitado).mock(return_value=httpx.Response(200, text="x"))
    with pytest.raises(DominioNaoPermitido):
        coletor._buscar(ORIGEM)
    assert not destino.called


@respx.mock
def test_redirect_para_http_puro_e_recusado(coletor):
    inseguro = "http://job-boards.greenhouse.io/x/jobs"
    respx.get(ORIGEM).mock(return_value=_redireciona(inseguro))
    destino = respx.get(inseguro).mock(return_value=httpx.Response(200, text="x"))
    with pytest.raises(ValueError, match="https"):
        coletor._buscar(ORIGEM)
    assert not destino.called


@respx.mock
def test_redirect_para_host_permitido_com_robots_proibindo_nao_e_requisitado(coletor):
    respx.get(ORIGEM).mock(return_value=_redireciona(DESTINO_PERMITIDO))
    respx.get("https://job-boards.greenhouse.io/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_BLOQUEIA)
    )
    destino = respx.get(DESTINO_PERMITIDO).mock(return_value=httpx.Response(200, text="x"))
    with pytest.raises(ValueError, match="robots"):
        coletor._buscar(ORIGEM)
    assert not destino.called


@respx.mock
def test_redirect_para_host_permitido_e_liberado_pelo_robots_e_seguido(coletor):
    respx.get(ORIGEM).mock(return_value=_redireciona(DESTINO_PERMITIDO))
    respx.get("https://job-boards.greenhouse.io/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_PERMITE)
    )
    respx.get(DESTINO_PERMITIDO).mock(return_value=httpx.Response(200, text="ok"))
    assert coletor._buscar(ORIGEM).text == "ok"


@respx.mock
def test_cadeia_de_redirects_acima_do_limite_da_config_e_recusada(coletor):
    limite = int(carregar("limites")["rede"]["redirecionamentos_max"])
    respx.get("https://job-boards.greenhouse.io/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_PERMITE)
    )
    respx.get("https://boards-api.greenhouse.io/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_PERMITE)
    )
    respx.get(ORIGEM).mock(return_value=_redireciona(ORIGEM))
    with pytest.raises(ValueError, match="redirecionamentos"):
        coletor._buscar(ORIGEM)
    buscas = [c for c in respx.calls if c.request.url.path != "/robots.txt"]
    assert len(buscas) == limite + 1
