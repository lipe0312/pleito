from __future__ import annotations

import httpx
import pytest
import respx

from src.coletor.conformidade import Limitador
from src.coletor.contratos import ModeloTrabalho, MotivoNoGo, Senioridade
from src.coletor.personio import FontePersonio
from src.coletor.smartrecruiters import FonteSmartRecruiters
from src.coletor.workable import FonteWorkable
from tests.apoio_ats import (
    PERSONIO,
    ROBOTS_LIVRE,
    SMARTRECRUITERS,
    TERMOS_PENDENTES,
    WORKABLE,
    aplicar,
    configuracao,
)

URL_WORKABLE = "https://apply.workable.com/api/v1/widget/accounts/acme?details=true"
URL_SR = "https://api.smartrecruiters.com/v1/companies/AcmeSR/postings"
URL_PERSONIO = "https://acme.jobs.personio.de/xml"


def _coletor(classe):
    cliente = httpx.Client()
    coletor = classe(client=cliente)
    coletor._limitador = Limitador(0)
    return coletor


def _robots(mock, *hosts):
    for host in hosts:
        mock.get(f"https://{host}/robots.txt").respond(200, text=ROBOTS_LIVRE)


@pytest.fixture(autouse=True)
def config(monkeypatch):
    aplicar(monkeypatch, configuracao())


def test_workable_traduz_vaga_e_descarta_a_sem_titulo():
    with respx.mock() as mock:
        _robots(mock, "apply.workable.com")
        mock.get(URL_WORKABLE).respond(200, json=WORKABLE)
        resultado = _coletor(FonteWorkable).coletar(10)
    assert [v.id_externo for v in resultado.vagas] == ["AB12"]
    vaga = resultado.vagas[0]
    assert vaga.fonte == "workable"
    assert vaga.empresa == "Acme Ficticia"
    assert vaga.senioridade is Senioridade.ESTAGIO
    assert vaga.pais == "BR"
    assert "<p>" not in vaga.descricao
    assert resultado.erro is None


def test_smartrecruiters_traduz_nivel_pais_modelo_e_url_publica():
    with respx.mock() as mock:
        _robots(mock, "api.smartrecruiters.com")
        mock.get(URL_SR).respond(200, json=SMARTRECRUITERS)
        resultado = _coletor(FonteSmartRecruiters).coletar(10)
    junior, estagio = resultado.vagas
    assert junior.url == "https://jobs.smartrecruiters.com/AcmeSR/7440001"
    assert junior.senioridade is Senioridade.JUNIOR
    assert junior.modelo is ModeloTrabalho.REMOTO
    assert junior.pais == "BR"
    assert estagio.senioridade is Senioridade.ESTAGIO


def test_personio_le_xml_e_monta_url_da_vaga():
    with respx.mock() as mock:
        _robots(mock, "acme.jobs.personio.de")
        mock.get(URL_PERSONIO).respond(200, text=PERSONIO)
        resultado = _coletor(FontePersonio).coletar(10)
    vaga = resultado.vagas[0]
    assert vaga.url == "https://acme.jobs.personio.de/job/991"
    assert vaga.senioridade is Senioridade.ESTAGIO
    assert "testes" in vaga.descricao
    assert vaga.publicada_em.isoformat() == "2026-10-20"


def test_personio_com_xml_malformado_vira_erro_sem_vagas():
    with respx.mock() as mock:
        _robots(mock, "acme.jobs.personio.de")
        mock.get(URL_PERSONIO).respond(200, text="<workzag-jobs><position>")
        resultado = _coletor(FontePersonio).coletar(10)
    assert resultado.vagas == []
    assert resultado.evidencia["falhas"]["acme"].startswith("xml invalido")


def test_personio_recusa_entidade_externa_no_xml():
    xml = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        "<workzag-jobs><position><id>1</id><name>&e;</name></position></workzag-jobs>"
    )
    with respx.mock() as mock:
        _robots(mock, "acme.jobs.personio.de")
        mock.get(URL_PERSONIO).respond(200, text=xml)
        resultado = _coletor(FontePersonio).coletar(10)
    assert resultado.vagas == []


@pytest.mark.parametrize(
    "classe,hosts,url",
    [
        (FonteWorkable, ["apply.workable.com"], URL_WORKABLE),
        (FonteSmartRecruiters, ["api.smartrecruiters.com"], URL_SR),
        (FontePersonio, ["acme.jobs.personio.de"], URL_PERSONIO),
    ],
)
def test_fonte_sem_termos_revisados_nao_coleta(monkeypatch, classe, hosts, url):
    config = configuracao()
    config["fontes"][classe.slug]["termos"] = TERMOS_PENDENTES
    aplicar(monkeypatch, config)
    with respx.mock(assert_all_called=False) as mock:
        rota = mock.get(url).respond(200, json={})
        robots = mock.get(f"https://{hosts[0]}/robots.txt").respond(200, text=ROBOTS_LIVRE)
        resultado = _coletor(classe).coletar(10)
    assert rota.call_count == 0
    assert robots.call_count == 0
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos
    assert resultado.vagas == []


@pytest.mark.parametrize("classe", [FonteWorkable, FonteSmartRecruiters, FontePersonio])
def test_fonte_desligada_nao_coleta(monkeypatch, classe):
    config = configuracao()
    config["fontes"][classe.slug]["ativa"] = False
    aplicar(monkeypatch, config)
    with respx.mock(assert_all_called=False) as mock:
        resultado = _coletor(classe).coletar(10)
        assert not mock.calls
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos


def test_redirect_para_fora_da_allowlist_e_recusado_sem_requisitar_o_destino():
    destino = "https://servidor-externo.example.net/vagas"
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock, "apply.workable.com")
        mock.get(URL_WORKABLE).respond(302, headers={"Location": destino})
        externo = mock.get(destino).respond(200, json=WORKABLE)
        resultado = _coletor(FonteWorkable).coletar(10)
    assert externo.call_count == 0
    assert resultado.vagas == []
    assert "nao esta em config/fontes.yaml" in resultado.evidencia["falhas"]["acme"]


def test_redirect_do_personio_para_subdominio_imitador_e_recusado():
    destino = "https://acme.jobs.personio.de.evil.com/xml"
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock, "acme.jobs.personio.de")
        mock.get(URL_PERSONIO).respond(302, headers={"Location": destino})
        externo = mock.get(destino).respond(200, text=PERSONIO)
        resultado = _coletor(FontePersonio).coletar(10)
    assert externo.call_count == 0
    assert resultado.vagas == []


@pytest.mark.parametrize("identificador", ["acme/../x", "a@evil.com", "acme.evil.com", "a b", "x#"])
def test_identificador_com_caractere_de_url_nunca_vira_requisicao(monkeypatch, identificador):
    config = configuracao()
    config["empresas_alvo"] = [{"nome": "Ruim", "ats": {"personio": identificador}}]
    aplicar(monkeypatch, config)
    with respx.mock(assert_all_called=False) as mock:
        resultado = _coletor(FontePersonio).coletar(10)
        assert not mock.calls
    assert resultado.vagas == []
    assert "identificador" in resultado.evidencia["falhas"][identificador]


def test_empresa_sem_board_do_ats_e_ignorada_e_sem_alvos_vira_sem_dados(monkeypatch):
    config = configuracao()
    config["empresas_alvo"] = [{"nome": "Beta Dados", "ats": {}}]
    aplicar(monkeypatch, config)
    with respx.mock(assert_all_called=False) as mock:
        resultado = _coletor(FonteWorkable).coletar(10)
        assert not mock.calls
    assert MotivoNoGo.SEM_DADOS in resultado.motivos


def test_robots_proibindo_o_host_da_empresa_nao_requisita_a_api():
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://apply.workable.com/robots.txt").respond(
            200, text="User-agent: *\nDisallow: /\n"
        )
        api = mock.get(URL_WORKABLE).respond(200, json=WORKABLE)
        resultado = _coletor(FonteWorkable).coletar(10)
    assert api.call_count == 0
    assert MotivoNoGo.ROBOTS_PROIBE in resultado.motivos
    assert resultado.robots_permite is False


def test_limite_de_vagas_e_respeitado():
    with respx.mock() as mock:
        _robots(mock, "api.smartrecruiters.com")
        mock.get(URL_SR).respond(200, json=SMARTRECRUITERS)
        resultado = _coletor(FonteSmartRecruiters).coletar(1)
    assert len(resultado.vagas) == 1
