from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.coletor.descoberta import descobrir
from src.coletor.workable import FonteWorkable
from tests.apoio_ats import (
    ROBOTS_LIVRE,
    SMARTRECRUITERS,
    TERMOS_PENDENTES,
    WORKABLE,
    aplicar,
    configuracao,
    sem_espera,
)


def _empresas(*itens):
    return [{"nome": nome, "ats": {}} for nome in itens]


@pytest.fixture(autouse=True)
def ambiente_de_teste(monkeypatch):
    aplicar(monkeypatch, configuracao())
    sem_espera(monkeypatch)


def _robots(mock):
    mock.get(url__regex=r"https://[^/]+/robots\.txt").respond(200, text=ROBOTS_LIVRE)


def test_tentativa_que_acha_vagas_vira_sugestao_gravada_em_arquivo(tmp_path):
    saida = tmp_path / "ats.json"
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        mock.get(
            "https://apply.workable.com/api/v1/widget/accounts/novaempresa?details=true"
        ).respond(200, json=WORKABLE)
        mock.get(
            url__regex=r"https://api\.smartrecruiters\.com/v1/companies/.*/postings"
        ).respond(404)
        mock.get(url__regex=r"https://.*\.jobs\.personio\.de/xml").respond(404)
        resultado = descobrir(_empresas("Nova Empresa"), cliente=httpx.Client(), saida=saida)
    gravado = json.loads(saida.read_text())
    assert gravado["sugestoes"] == [
        {"empresa": "Nova Empresa", "ats": "workable", "identificador": "novaempresa", "vagas": 1}
    ]
    assert resultado == gravado["sugestoes"]


def test_sugestao_nao_ativa_a_empresa_na_coleta(tmp_path, monkeypatch):
    config = configuracao()
    config["empresas_alvo"] = _empresas("Nova Empresa")
    aplicar(monkeypatch, config)
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        mock.get(
            "https://apply.workable.com/api/v1/widget/accounts/novaempresa?details=true"
        ).respond(200, json=WORKABLE)
        mock.get(url__regex=r"https://api\.smartrecruiters\.com/.*").respond(404)
        mock.get(url__regex=r"https://.*\.jobs\.personio\.de/xml").respond(404)
        descobrir(config["empresas_alvo"], cliente=httpx.Client(), saida=tmp_path / "ats.json")
        assert config["empresas_alvo"] == _empresas("Nova Empresa")
        antes = len(mock.calls)
        resultado = FonteWorkable(client=httpx.Client()).coletar(10)
        assert len(mock.calls) == antes
    assert resultado.vagas == []


def test_candidato_inexistente_nao_gera_sugestao(tmp_path):
    saida = tmp_path / "ats.json"
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        mock.get(url__regex=r"https://apply\.workable\.com/.*").respond(404)
        mock.get(url__regex=r"https://api\.smartrecruiters\.com/.*").respond(404)
        mock.get(url__regex=r"https://.*\.jobs\.personio\.de/xml").respond(404)
        descobrir(_empresas("Nao Existe"), cliente=httpx.Client(), saida=saida)
    assert json.loads(saida.read_text())["sugestoes"] == []


def test_quadro_vazio_com_200_nao_vira_sugestao(tmp_path):
    saida = tmp_path / "ats.json"
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        mock.get(url__regex=r"https://apply\.workable\.com/.*").respond(200, json={"jobs": []})
        mock.get(url__regex=r"https://api\.smartrecruiters\.com/.*").respond(
            200, json={"content": []}
        )
        mock.get(url__regex=r"https://.*\.jobs\.personio\.de/xml").respond(404)
        descobrir(_empresas("Vazia"), cliente=httpx.Client(), saida=saida)
    assert json.loads(saida.read_text())["sugestoes"] == []


def test_ats_sem_termos_revisados_nao_e_sondado(tmp_path, monkeypatch):
    config = configuracao()
    config["fontes"]["workable"]["termos"] = TERMOS_PENDENTES
    aplicar(monkeypatch, config)
    saida = tmp_path / "ats.json"
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        workable = mock.get(url__regex=r"https://apply\.workable\.com/.*").respond(
            200, json=WORKABLE
        )
        mock.get(url__regex=r"https://api\.smartrecruiters\.com/.*").respond(
            200, json=SMARTRECRUITERS
        )
        mock.get(url__regex=r"https://.*\.jobs\.personio\.de/xml").respond(404)
        descobrir(_empresas("Nova Empresa"), cliente=httpx.Client(), saida=saida)
    assert workable.call_count == 0
    assert {s["ats"] for s in json.loads(saida.read_text())["sugestoes"]} == {"smartrecruiters"}


def test_numero_de_candidatos_por_ats_respeita_o_limite_da_config(tmp_path, monkeypatch):
    config = configuracao()
    config["ats"]["candidatos_max"] = 2
    aplicar(monkeypatch, config)
    empresa = {"nome": "Nova Empresa", "ats": {}, "candidatos": ["a1", "a2", "a3", "a4", "a5"]}
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        workable = mock.get(url__regex=r"https://apply\.workable\.com/api/.*").respond(404)
        mock.get(url__regex=r"https://api\.smartrecruiters\.com/.*").respond(404)
        mock.get(url__regex=r"https://.*\.jobs\.personio\.de/xml").respond(404)
        descobrir([empresa], cliente=httpx.Client(), saida=tmp_path / "ats.json")
    assert workable.call_count == 2


def test_empresa_que_ja_tem_board_do_ats_nao_e_sondada_nesse_ats(tmp_path):
    empresa = {"nome": "Acme Ficticia", "ats": {"workable": "acme"}}
    with respx.mock(assert_all_called=False) as mock:
        _robots(mock)
        workable = mock.get(url__regex=r"https://apply\.workable\.com/api/.*").respond(200)
        mock.get(url__regex=r"https://api\.smartrecruiters\.com/.*").respond(404)
        mock.get(url__regex=r"https://.*\.jobs\.personio\.de/xml").respond(404)
        descobrir([empresa], cliente=httpx.Client(), saida=tmp_path / "ats.json")
    assert workable.call_count == 0
