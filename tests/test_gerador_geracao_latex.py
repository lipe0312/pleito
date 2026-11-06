from __future__ import annotations

import shutil

import pytest
from apoio_geracao import (
    FAMILIAS,
    IDIOMAS,
    INJECAO,
    VAGA,
    conteudo_ampliado,
    roteador_falso,
    slots_ia_validos,
)
from apoio_gerador import travado_ficticio
from pypdf import PdfReader

from src.gerador.compilar import compilar
from src.gerador.configuracao import configuracao_gerador
from src.gerador.gerar import gerar_curriculo, gerar_sem_ia

pytestmark = pytest.mark.latex

BLOCOS, INVENTARIO = conteudo_ampliado()
TRAVADO = travado_ficticio()


@pytest.fixture(scope="module")
def config():
    configuracao = configuracao_gerador()
    if shutil.which(configuracao.compilacao.motor) is None:
        pytest.skip(f"{configuracao.compilacao.motor} nao instalado")
    return configuracao


def _texto(pdf) -> str:
    return " ".join(pagina.extract_text() for pagina in PdfReader(pdf).pages)


@pytest.mark.parametrize("familia", FAMILIAS)
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_modo_sem_ia_gera_as_quatro_familias_que_compilam_em_uma_pagina(
    config, tmp_path, familia, idioma
):
    resultado = gerar_sem_ia(familia, idioma, "", BLOCOS, INVENTARIO, TRAVADO)

    pdf = compilar(resultado.tex, tmp_path, config)

    assert len(PdfReader(pdf).pages) == 1
    assert "PESSOA FICTICIA" in _texto(pdf)


def test_injecao_vira_texto_inerte_no_pdf(config, tmp_path):
    slots = slots_ia_validos(BLOCOS)
    slots["sobre"]["texto"] = r"\input{/etc/passwd}"
    roteador, _ = roteador_falso(slots)

    resultado = gerar_curriculo(
        "backend_arquitetura", "pt", f"{VAGA}\n{INJECAO}", BLOCOS, INVENTARIO, TRAVADO, roteador
    )
    pdf = compilar(resultado.tex, tmp_path, config)

    assert "root:" not in _texto(pdf)
    assert "input" in _texto(pdf)
