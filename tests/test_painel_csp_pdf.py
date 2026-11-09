from __future__ import annotations

from pathlib import Path

import pytest
from apoio_painel_telas import CONFIG, montar


def diretivas(resposta) -> dict[str, str]:
    politica = resposta.headers["content-security-policy"]
    return dict(parte.strip().split(" ", 1) for parte in politica.split(";"))


@pytest.fixture
def cliente():
    return montar()


@pytest.mark.parametrize(
    "rota", ["/hoje", "/candidaturas", "/curriculos", "/curriculos/vaga/101", "/projetos"]
)
def test_paginas_so_ganham_frame_src_self_e_continuam_sem_ser_embutiveis(cliente, rota):
    resposta = cliente.get(rota)
    politica = diretivas(resposta)
    assert politica["frame-src"] == "'self'"
    assert politica["frame-ancestors"] == "'none'"
    assert resposta.headers["x-frame-options"] == "DENY"


def test_csp_so_difere_da_do_f1_8_pelo_frame_src(cliente):
    politica = diretivas(cliente.get("/hoje"))
    esperado = {k: v for k, v in CONFIG["csp"].items()}
    assert politica == esperado
    assert set(politica) - {"frame-src"} == {
        "default-src",
        "script-src",
        "style-src",
        "img-src",
        "connect-src",
        "form-action",
        "base-uri",
        "frame-ancestors",
    }
    assert politica["default-src"] == "'none'"
    assert politica["script-src"] == "'self'"
    assert politica["connect-src"] == "'self'"


def test_so_a_rota_do_pdf_aceita_ser_embutida_e_so_pelo_proprio_painel(cliente):
    pdf = cliente.get("/pdf/vaga/101")
    politica = diretivas(pdf)
    assert politica["frame-ancestors"] == "'self'"
    assert pdf.headers["x-frame-options"] == "SAMEORIGIN"
    assert politica["default-src"] == "'none'"
    assert "object-src" not in politica
    assert "*" not in pdf.headers["content-security-policy"]


def test_o_pdf_que_nao_existe_tambem_sai_com_os_cabecalhos_do_pdf_e_nao_vaza_outra_rota(cliente):
    assert cliente.get("/pdf/vaga/999").headers["x-frame-options"] == "SAMEORIGIN"
    assert cliente.get("/assets/painel.css").headers["x-frame-options"] == "DENY"
    assert cliente.get("/rota-que-nao-existe").headers["x-frame-options"] == "DENY"


def test_mudanca_de_csp_tem_adr_propria():
    adrs = sorted(Path("docs/adr").glob("*.md"))
    textos = [caminho.read_text(encoding="utf-8") for caminho in adrs]
    assert any("frame-src" in texto and "frame-ancestors" in texto for texto in textos)
