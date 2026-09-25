from __future__ import annotations

import httpx
import pytest

from viabilidade.conformidade import (
    DominioNaoPermitido,
    Limitador,
    consultar_robots,
    dominios_permitidos,
    exigir_dominio_permitido,
)

ROBOTS_BLOQUEIA = "User-agent: *\nDisallow: /api/\n"
ROBOTS_LIBERA = "User-agent: *\nAllow: /\nCrawl-delay: 3\n"


def _client(texto: str, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=texto)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_dominio_fora_do_yaml_e_bloqueado():
    with pytest.raises(DominioNaoPermitido):
        exigir_dominio_permitido("https://exemplo-aleatorio.com/vagas")


def test_dominio_do_yaml_passa():
    assert exigir_dominio_permitido("https://boards-api.greenhouse.io/v1/boards/x/jobs")


def test_linkedin_nunca_entra_nos_dominios_permitidos():
    assert not any("linkedin" in d for d in dominios_permitidos())


def test_robots_disallow_bloqueia():
    with _client(ROBOTS_BLOQUEIA) as c:
        d = consultar_robots("https://portal.api.gupy.io/api/v1/jobs", c)
    assert d.permitido is False
    assert d.robots_encontrado is True


def test_robots_allow_permite_e_le_crawl_delay():
    with _client(ROBOTS_LIBERA) as c:
        d = consultar_robots("https://portal.api.gupy.io/api/v1/jobs", c)
    assert d.permitido is True
    assert d.crawl_delay == 3.0


def test_robots_ausente_libera():
    with _client("", status=404) as c:
        d = consultar_robots("https://boards-api.greenhouse.io/v1/boards/x/jobs", c)
    assert d.permitido is True
    assert d.robots_encontrado is False


def test_robots_com_erro_de_servidor_nao_libera():
    with _client("", status=500) as c:
        d = consultar_robots("https://portal.api.gupy.io/api/v1/jobs", c)
    assert d.permitido is False


def test_limitador_respeita_intervalo():
    import time

    lim = Limitador(rps=20)
    lim.esperar()
    inicio = time.monotonic()
    lim.esperar()
    assert time.monotonic() - inicio >= 0.04
