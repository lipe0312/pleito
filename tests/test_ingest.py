from __future__ import annotations

import json

import httpx
import pytest

from viabilidade.contratos import ModeloTrabalho, Senioridade
from viabilidade.ingest.base import ColetorHttp, inferir_modelo, inferir_senioridade
from viabilidade.ingest.greenhouse import limpar_html, parse_jobs
from viabilidade.ingest.lever import parse_postings


class ColetorFalso(ColetorHttp):
    slug = "greenhouse"

    def __init__(self) -> None:
        self._client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
        self._proprio = True
        from viabilidade.conformidade import Limitador

        self._limitador = Limitador(0)


@pytest.fixture
def coletor() -> ColetorFalso:
    c = ColetorFalso()
    yield c
    c.fechar()


def test_limpar_html_remove_tags_e_entidades():
    assert limpar_html("<p>Python&nbsp;&amp; SQL</p>") == "Python & SQL"


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Software Engineer Intern", Senioridade.ESTAGIO),
        ("Estagio em Desenvolvimento", Senioridade.ESTAGIO),
        ("Senior Backend Engineer", Senioridade.SENIOR),
        ("Staff Engineer", Senioridade.SENIOR),
        ("Desenvolvedor Pleno", Senioridade.PLENO),
        ("Junior Data Analyst", Senioridade.JUNIOR),
        ("Product Manager", Senioridade.INDEFINIDA),
    ],
)
def test_inferir_senioridade(texto, esperado):
    assert inferir_senioridade(texto) is esperado


def test_estagio_vence_senior_no_mesmo_texto():
    assert inferir_senioridade("Intern reporting to a senior engineer") is Senioridade.ESTAGIO


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Remote - Brazil", ModeloTrabalho.REMOTO),
        ("Hybrid, Sao Paulo", ModeloTrabalho.HIBRIDO),
        ("On-site Berlin", ModeloTrabalho.PRESENCIAL),
        ("Sao Paulo", ModeloTrabalho.INDEFINIDO),
    ],
)
def test_inferir_modelo(texto, esperado):
    assert inferir_modelo(texto) is esperado


def test_parse_greenhouse_normaliza_e_descarta_url_insegura(coletor, fixtures):
    payload = json.loads((fixtures / "greenhouse_jobs.json").read_text(encoding="utf-8"))
    vagas = parse_jobs(payload, "nubank", coletor)
    assert len(vagas) == 2
    estagio = next(v for v in vagas if v.id_externo == "4567")
    assert estagio.senioridade is Senioridade.ESTAGIO
    assert estagio.modelo is ModeloTrabalho.REMOTO
    assert estagio.publicada_em.isoformat() == "2026-09-10"
    assert estagio.completude == 1.0
    assert "<p>" not in estagio.descricao


def test_parse_greenhouse_marca_senior(coletor, fixtures):
    payload = json.loads((fixtures / "greenhouse_jobs.json").read_text(encoding="utf-8"))
    senior = next(v for v in parse_jobs(payload, "nubank", coletor) if v.id_externo == "4568")
    assert senior.senioridade is Senioridade.SENIOR


def test_parse_lever_converte_timestamp_ms(coletor, fixtures):
    payload = json.loads((fixtures / "lever_postings.json").read_text(encoding="utf-8"))
    vagas = parse_postings(payload, "hotmart", coletor)
    assert len(vagas) == 1
    assert vagas[0].senioridade is Senioridade.JUNIOR
    assert vagas[0].modelo is ModeloTrabalho.REMOTO
    assert vagas[0].publicada_em is not None


def test_coletor_recusa_dominio_fora_do_yaml(coletor):
    from viabilidade.conformidade import DominioNaoPermitido

    with pytest.raises(DominioNaoPermitido):
        coletor._buscar("https://sitequalquer.com/api")


def test_rss_recusa_entidade_externa():
    from defusedxml.common import EntitiesForbidden

    from viabilidade.ingest.rss import fromstring_seguro

    ataque = (
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<rss><channel><item><title>&x;</title></item></channel></rss>"
    )
    with pytest.raises(EntitiesForbidden):
        fromstring_seguro(ataque)


def test_rss_recusa_bomba_de_entidades():
    from defusedxml.common import EntitiesForbidden

    from viabilidade.ingest.rss import fromstring_seguro

    bomba = (
        b'<?xml version="1.0"?><!DOCTYPE b [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
        b"<rss><channel><item><title>&b;</title></item></channel></rss>"
    )
    with pytest.raises(EntitiesForbidden):
        fromstring_seguro(bomba)


@pytest.mark.parametrize(
    "titulo,descricao,esperado",
    [
        (
            "Estagiario(a) de Servicos",
            "Trataremos seus dados pessoais conforme a LGPD",
            "indefinida",
        ),
        ("Estagio em Suporte", "Voce cuidara dos dados cadastrais dos clientes", "indefinida"),
        ("Estagio em Analise de Dados", "", "dados"),
        ("Data Analyst Intern", "", "dados"),
        ("Analista de BI Junior", "", "dados"),
        ("Assistente Administrativo", "Cadastro de dados no sistema", "outra"),
        ("Analista de BI Pleno", "", "dados"),
        ("Estagio em ETL", "", "dados"),
        ("Bibliotecario", "", "indefinida"),
        ("Analista de QA Junior", "", "qa"),
        ("Estagio", "Voce vai construir pipelines com data engineer no time", "dados"),
    ],
)
def test_palavra_generica_nao_classifica_pela_descricao(titulo, descricao, esperado):
    from viabilidade.triagem import inferir_funcao

    assert inferir_funcao(titulo, descricao).value == esperado
