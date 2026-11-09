from __future__ import annotations

import shutil

import pytest
from apoio_laco import com_quatro_projetos, configuracao, pedido, roteador_em_sequencia
from pypdf import PdfReader

from src.gerador.laco import Estado, executar_laco

pytestmark = pytest.mark.latex


@pytest.fixture(autouse=True)
def _motor():
    if shutil.which(configuracao().compilacao.motor) is None:
        pytest.skip("pdflatex nao instalado")


def test_laco_com_pdflatex_real_publica_pdf_de_uma_pagina(tmp_path):
    roteador, rastro = roteador_em_sequencia([com_quatro_projetos()])

    resultado = executar_laco(pedido(), tmp_path, roteador, config=configuracao(tentativas_max=1))

    assert resultado.estado is Estado.APROVADO
    assert len(rastro.pedidos) == 1
    assert len(PdfReader(tmp_path / "cv.pdf").pages) == 1
    assert (tmp_path / "tentativas/1/cv.log").is_file()
