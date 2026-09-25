from __future__ import annotations

from pathlib import Path

import pytest

from viabilidade.contratos import Funcao, ModeloTrabalho, Senioridade
from viabilidade.ingest.email_alertas import (
    coletar_de_emails,
    extrair_alerta_linkedin,
    remetente_confiavel,
)

CORPO = (Path(__file__).parent / "fixtures" / "linkedin_alerta.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "remetente",
    [
        "jobs-noreply@linkedin.com",
        "JOBS-NOREPLY@LINKEDIN.COM",
        "jobalerts-noreply@linkedin.com",
        "LinkedIn <jobs-noreply@linkedin.com>",
    ],
)
def test_remetente_do_linkedin_e_aceito(remetente):
    assert remetente_confiavel(remetente)


@pytest.mark.parametrize(
    "remetente",
    [
        "golpe@nao-linkedin.com",
        "jobs-noreply@linkedin.com.golpe.net",
        "phishing@linkedin.com.br",
        "jobs-noreply@evil.com",
        "jobs-noreply@sub.linkedin.com",
        "jobs-noreply@linkedin.com@evil.com",
        "qualquer@linkedin.com",
        "",
    ],
)
def test_remetente_forjado_e_recusado(remetente):
    assert not remetente_confiavel(remetente)
    assert extrair_alerta_linkedin(remetente, CORPO) == []


def test_extrai_vagas_do_alerta_real():
    vagas = extrair_alerta_linkedin("jobs-noreply@linkedin.com", CORPO)
    assert len(vagas) == 3
    assert [v.id_externo for v in vagas] == ["4470629685", "4447008117", "4400000001"]


def test_campos_vem_alinhados():
    primeira = extrair_alerta_linkedin("jobs-noreply@linkedin.com", CORPO)[0]
    assert primeira.titulo == "Jovem Aprendiz - Base Salvador"
    assert primeira.empresa == "Capgemini"
    assert primeira.local == "Salvador"
    assert primeira.senioridade is Senioridade.ESTAGIO


def test_vaga_remota_de_dados_e_classificada():
    ultima = extrair_alerta_linkedin("jobs-noreply@linkedin.com", CORPO)[-1]
    assert ultima.modelo is ModeloTrabalho.REMOTO
    assert ultima.funcao is Funcao.DADOS
    assert ultima.senioridade is Senioridade.ESTAGIO


def test_link_de_busca_e_cabecalho_sao_ignorados():
    vagas = extrair_alerta_linkedin("jobs-noreply@linkedin.com", CORPO)
    assert all("search-results" not in v.url for v in vagas)
    assert all(v.empresa != "desconhecida" for v in vagas)


def test_url_gerada_nao_carrega_token_de_rastreio():
    for vaga in extrair_alerta_linkedin("jobs-noreply@linkedin.com", CORPO):
        assert vaga.url.startswith("https://www.linkedin.com/jobs/view/")
        assert "trackingId" not in vaga.url
        assert "?" not in vaga.url


def test_coletor_conta_emails_descartados():
    r = coletar_de_emails(
        [("jobs-noreply@linkedin.com", CORPO), ("spam@qualquer.com", CORPO)]
    )
    assert len(r.vagas) == 3
    assert r.evidencia["emails_descartados_por_remetente"] == 1
    assert r.robots_permite is None
