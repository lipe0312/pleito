from __future__ import annotations

import shutil

import pytest
from apoio_validador import inventario_ficticio, tex_ficticio

from src.gerador.compilar import compilar
from src.gerador.configuracao import configuracao_gerador
from src.validador.paginas import texto_do_pdf
from src.validador.validar import validar_curriculo

pytestmark = pytest.mark.latex


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_pdf_compilado_do_template_passa_em_todas_as_regras(tmp_path, idioma):
    config = configuracao_gerador()
    if shutil.which(config.compilacao.motor) is None:
        pytest.skip(f"{config.compilacao.motor} nao instalado")
    tex = tex_ficticio(idioma)
    pdf = compilar(tex, tmp_path, config)

    resultado = validar_curriculo(tex, inventario_ficticio(), pdf=pdf)

    assert resultado.aprovado, resultado.violacoes
    assert "Python" in texto_do_pdf(pdf)
