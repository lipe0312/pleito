from __future__ import annotations

import httpx
import pytest

from src.coletor.conformidade import (
    DominioNaoPermitido,
    Limitador,
    consultar_robots,
    dominios_permitidos,
    exigir_dominio_permitido,
)
from src.config import carregar

ROBOTS_BLOQUEIA = "User-agent: *\nDisallow: /v1/\n"
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


def test_subdominio_de_dominio_permitido_passa():
    assert exigir_dominio_permitido("https://eu.jobs.lever.co/abc") == "eu.jobs.lever.co"


def test_dominio_que_apenas_termina_igual_e_bloqueado():
    with pytest.raises(DominioNaoPermitido):
        exigir_dominio_permitido("https://malicioso-jobs.lever.co/abc")


def test_sufixo_nao_vale_sem_ponto():
    with pytest.raises(DominioNaoPermitido):
        exigir_dominio_permitido("https://fakejobs.lever.co/abc")


def test_linkedin_nunca_entra_nos_dominios_permitidos():
    assert not any("linkedin" in d for d in dominios_permitidos())


def test_robots_disallow_bloqueia():
    with _client(ROBOTS_BLOQUEIA) as c:
        d = consultar_robots("https://boards-api.greenhouse.io/v1/boards/x/jobs", c)
    assert d.permitido is False
    assert d.robots_encontrado is True


def test_robots_allow_permite_e_le_crawl_delay():
    with _client(ROBOTS_LIBERA) as c:
        d = consultar_robots("https://boards-api.greenhouse.io/v1/boards/x/jobs", c)
    assert d.permitido is True
    assert d.crawl_delay == 3.0


@pytest.mark.parametrize("status", [401, 403, 404, 410, 451])
def test_robots_indisponivel_4xx_libera_conforme_rfc9309(status):
    with _client("", status=status) as c:
        d = consultar_robots("https://boards-api.greenhouse.io/v1/boards/x/jobs", c)
    assert d.permitido is True
    assert d.robots_encontrado is False


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_robots_inacessivel_exige_recusa(status):
    with _client("", status=status) as c:
        d = consultar_robots("https://boards-api.greenhouse.io/v1/boards/x/jobs", c)
    assert d.permitido is False


def test_limitador_respeita_intervalo():
    import time

    lim = Limitador(rps=20)
    lim.esperar()
    inicio = time.monotonic()
    lim.esperar()
    assert time.monotonic() - inicio >= 0.04


@pytest.mark.parametrize(
    "url",
    [
        "https://greenhouse.io.evil.com/v1/boards/x/jobs",
        "https://evilgreenhouse.io/v1/boards/x/jobs",
        "https://boards-api.greenhouse.io.evil.com/v1/boards/x/jobs",
        "https://evil.com/boards-api.greenhouse.io",
    ],
)
def test_host_que_imita_dominio_permitido_e_bloqueado(url):
    with pytest.raises(DominioNaoPermitido):
        exigir_dominio_permitido(url)


def test_coletor_com_robots_proibindo_nao_chega_a_requisitar_a_api():
    from src.coletor.contratos import MotivoNoGo
    from src.coletor.greenhouse import FonteGreenhouse

    requisicoes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requisicoes.append(request.url.path)
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    resultado = FonteGreenhouse(client=cliente).coletar(5)
    assert requisicoes == ["/robots.txt"]
    assert MotivoNoGo.ROBOTS_PROIBE in resultado.motivos
    assert resultado.vagas == []


def test_gupy_nunca_entra_na_allowlist_nem_no_registro_de_fontes():
    from viabilidade.ingest import registro

    assert not any(d.endswith("gupy.io") for d in dominios_permitidos())
    assert "gupy" not in carregar("fontes")["fontes"]
    assert "gupy" not in registro()
    with pytest.raises(DominioNaoPermitido):
        exigir_dominio_permitido("https://portal.gupy.io/jobs")


def test_nenhuma_fonte_registrada_aponta_para_gupy():
    from src.coletor.base import registro

    assert not any("gupy" in slug for slug in registro())
