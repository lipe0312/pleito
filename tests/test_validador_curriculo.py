from __future__ import annotations

import pytest
from apoio_validador import gravar_pdf, inventario_ficticio, tex_com_corpo, tex_ficticio

from src.validador.resultado import CurriculoInvalido, Regra
from src.validador.validar import (
    exigir_arquivos_validos,
    exigir_fonte_valida,
    validar_arquivos,
    validar_fonte,
)


def test_curriculo_ficticio_de_uma_pagina_e_aprovado(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia, Python e PostgreSQL"])

    resultado = validar_arquivos(tex_ficticio(), inventario_ficticio(), pdf=pdf)

    assert resultado.aprovado
    assert resultado.violacoes == ()


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_fonte_limpa_passa_na_checagem_antes_de_compilar(idioma):
    assert validar_fonte(tex_ficticio(idioma), inventario_ficticio()).aprovado


def test_todas_as_violacoes_aparecem_juntas(tmp_path):
    pdf = gravar_pdf(tmp_path, ["um", "dois"])
    tex = tex_com_corpo("\\input{x} \\tech{Cobol} feito \u2014 pronto a\u200bb")

    resultado = validar_arquivos(tex, inventario_ficticio(), pdf=pdf)

    assert set(resultado.regras) == {
        Regra.PAGINAS,
        Regra.LATEX,
        Regra.TECNOLOGIA,
        Regra.TRAVESSAO,
        Regra.CARACTERE_INVISIVEL,
    }
    assert not resultado.aprovado


def test_exigir_arquivos_validos_levanta_com_as_regras_violadas():
    with pytest.raises(CurriculoInvalido) as erro:
        exigir_fonte_valida(tex_com_corpo("\\write18{x}"), inventario_ficticio())

    assert erro.value.resultado.regras == (Regra.LATEX,)
    assert "latex" in str(erro.value)


def test_exigir_arquivos_validos_nao_levanta_para_curriculo_limpo(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia"])

    exigir_arquivos_validos(tex_ficticio(), inventario_ficticio(), pdf=pdf)


def test_curriculo_sem_pdf_nao_e_aprovado_porque_paginas_nao_foram_conferidas():
    resultado = validar_arquivos(tex_ficticio(), inventario_ficticio())

    assert not resultado.aprovado
    assert resultado.regras == (Regra.PAGINAS,)


def test_exigir_arquivos_validos_sem_pdf_levanta():
    with pytest.raises(CurriculoInvalido) as erro:
        exigir_arquivos_validos(tex_ficticio(), inventario_ficticio())

    assert erro.value.resultado.regras == (Regra.PAGINAS,)


def test_checagem_so_da_fonte_nao_diz_nada_sobre_paginas():
    assert validar_fonte(tex_ficticio(), inventario_ficticio()).regras == ()


def test_exigir_fonte_valida_recusa_latex_malicioso_sem_precisar_de_pdf():
    with pytest.raises(CurriculoInvalido):
        exigir_fonte_valida(tex_com_corpo("\\write18{x}"), inventario_ficticio())


def test_pdf_de_duas_paginas_barra_mesmo_com_tex_limpo(tmp_path):
    pdf = gravar_pdf(tmp_path, ["um", "dois"])

    with pytest.raises(CurriculoInvalido):
        exigir_arquivos_validos(tex_ficticio(), inventario_ficticio(), pdf=pdf)
