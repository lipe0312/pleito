from __future__ import annotations

import time

import httpx
import pytest
import respx

from src.coletor.base import ColetorHttp
from src.coletor.conformidade import Limitador
from src.config import carregar
from tests.apoio_ats import aplicar, configuracao

URL = "https://api.smartrecruiters.com/v1/companies/AcmeSR/postings"
RPS = 20


class Coletor(ColetorHttp):
    slug = "smartrecruiters"


@pytest.fixture(autouse=True)
def config(monkeypatch):
    aplicar(monkeypatch, configuracao())


@pytest.fixture
def coletor():
    c = Coletor(client=httpx.Client())
    c._limitador = Limitador(RPS)
    c.esperas = []
    c._dormir = c.esperas.append
    return c


def _marcar(respostas: list, instantes: list):
    iterador = iter(respostas)

    def lado(request):
        instantes.append(time.monotonic())
        return next(iterador)

    return lado


@respx.mock
def test_429_seguido_de_200_e_coletado_sem_passar_do_rps(coletor):
    instantes: list[float] = []
    respx.get(URL).mock(
        side_effect=_marcar(
            [httpx.Response(429), httpx.Response(200, json={"content": []})], instantes
        )
    )
    resposta = coletor._buscar(URL)
    assert resposta.status_code == 200
    assert len(instantes) == 2
    assert instantes[1] - instantes[0] >= (1 / RPS) * 0.9
    assert coletor.esperas == [float(carregar("fontes")["backoff_429"]["base_s"])]


@respx.mock
def test_retry_after_maior_que_o_teto_e_cortado_no_teto_da_config(coletor):
    teto = float(carregar("fontes")["backoff_429"]["max_s"])
    respx.get(URL).mock(
        side_effect=_marcar(
            [httpx.Response(429, headers={"Retry-After": "9999"}), httpx.Response(200)], []
        )
    )
    coletor._buscar(URL)
    assert coletor.esperas == [teto]


@respx.mock
def test_retry_after_menor_que_o_backoff_nao_encurta_a_espera(coletor):
    base = float(carregar("fontes")["backoff_429"]["base_s"])
    respx.get(URL).mock(
        side_effect=_marcar(
            [httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(200)], []
        )
    )
    coletor._buscar(URL)
    assert coletor.esperas == [base]


@respx.mock
def test_429_persistente_para_no_limite_de_tentativas_e_devolve_o_429(coletor):
    tentativas = int(carregar("limites")["rede"]["tentativas"])
    rota = respx.get(URL).mock(return_value=httpx.Response(429))
    resposta = coletor._buscar(URL)
    assert resposta.status_code == 429
    assert rota.call_count == tentativas
    assert len(coletor.esperas) == tentativas - 1


@respx.mock
def test_backoff_dobra_a_cada_tentativa_ate_o_teto(coletor):
    cfg = carregar("fontes")["backoff_429"]
    respx.get(URL).mock(return_value=httpx.Response(429))
    coletor._buscar(URL)
    base, teto = float(cfg["base_s"]), float(cfg["max_s"])
    esperado = [min(base * 2**n, teto) for n in range(len(coletor.esperas))]
    assert coletor.esperas == esperado


@respx.mock
def test_resposta_200_nao_dorme(coletor):
    respx.get(URL).mock(return_value=httpx.Response(200))
    coletor._buscar(URL)
    assert coletor.esperas == []
