from __future__ import annotations

import httpx
import pytest
import respx

from src.coletor.rodada import formatar, rodar_fontes
from tests.apoio_ats import (
    PERSONIO,
    ROBOTS_LIVRE,
    SMARTRECRUITERS,
    TERMOS_PENDENTES,
    WORKABLE,
    aplicar,
    configuracao,
    sem_espera,
)

URL_WORKABLE = "https://apply.workable.com/api/v1/widget/accounts/acme?details=true"
URL_SR = "https://api.smartrecruiters.com/v1/companies/AcmeSR/postings"
URL_PERSONIO = "https://acme.jobs.personio.de/xml"


@pytest.fixture(autouse=True)
def ambiente_de_teste(monkeypatch):
    aplicar(monkeypatch, configuracao())
    sem_espera(monkeypatch)


def _robots(mock):
    for host in ("apply.workable.com", "api.smartrecruiters.com", "acme.jobs.personio.de"):
        mock.get(f"https://{host}/robots.txt").respond(200, text=ROBOTS_LIVRE)


def test_relatorio_traz_vagas_completude_e_erro_de_cada_fonte():
    with respx.mock() as mock:
        _robots(mock)
        mock.get(URL_WORKABLE).respond(200, json=WORKABLE)
        mock.get(URL_SR).respond(429)
        mock.get(URL_PERSONIO).respond(200, text=PERSONIO)
        relatorios = rodar_fontes(cliente=httpx.Client(), limite=20)
    por_fonte = {r.fonte: r for r in relatorios}
    assert set(por_fonte) == {"workable", "smartrecruiters", "personio"}
    assert por_fonte["workable"].vagas == 1
    assert 0 < por_fonte["workable"].completude <= 1
    assert por_fonte["smartrecruiters"].vagas == 0
    assert any("429" in erro for erro in por_fonte["smartrecruiters"].erros)
    assert por_fonte["personio"].vagas == 1


def test_fonte_desligada_aparece_no_relatorio_com_o_motivo(monkeypatch):
    config = configuracao()
    config["fontes"]["personio"]["termos"] = TERMOS_PENDENTES
    aplicar(monkeypatch, config)
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        mock.get(URL_WORKABLE).respond(200, json=WORKABLE)
        mock.get(URL_SR).respond(200, json=SMARTRECRUITERS)
        mock.get(URL_PERSONIO).respond(200, text=PERSONIO)
        relatorios = rodar_fontes(cliente=httpx.Client(), limite=20)
    personio = next(r for r in relatorios if r.fonte == "personio")
    assert personio.vagas == 0
    assert personio.ligada is False
    assert any("termos" in erro or "revisado_em" in erro for erro in personio.erros)


def test_fonte_abaixo_do_minimo_e_marcada_para_corte():
    with respx.mock() as mock:
        _robots(mock)
        mock.get(URL_WORKABLE).respond(200, json={"jobs": []})
        mock.get(URL_SR).respond(200, json=SMARTRECRUITERS)
        mock.get(URL_PERSONIO).respond(200, text=PERSONIO)
        relatorios = rodar_fontes(cliente=httpx.Client(), limite=20)
    por_fonte = {r.fonte: r for r in relatorios}
    assert por_fonte["workable"].rende is False
    assert por_fonte["smartrecruiters"].rende is True


def test_texto_do_relatorio_lista_uma_linha_por_fonte():
    with respx.mock() as mock:
        _robots(mock)
        mock.get(URL_WORKABLE).respond(200, json=WORKABLE)
        mock.get(URL_SR).respond(200, json=SMARTRECRUITERS)
        mock.get(URL_PERSONIO).respond(200, text=PERSONIO)
        texto = formatar(rodar_fontes(cliente=httpx.Client(), limite=20))
    linhas = texto.splitlines()
    assert len(linhas) == 3
    assert linhas[0].startswith("workable")
    assert "vagas=1" in linhas[0]
