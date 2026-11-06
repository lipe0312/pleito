from __future__ import annotations

import pytest
from apoio_validador import gravar_pdf, inventario_ficticio, tex_com_corpo, tex_ficticio

from src.validador.resultado import CurriculoInvalido, Regra
from src.validador.validar import exigir_valido, validar_curriculo


def test_curriculo_ficticio_de_uma_pagina_e_aprovado(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia, Python e PostgreSQL"])

    resultado = validar_curriculo(tex_ficticio(), inventario_ficticio(), pdf=pdf)

    assert resultado.aprovado
    assert resultado.violacoes == ()


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_tex_sem_pdf_e_validado_antes_de_compilar(idioma):
    assert validar_curriculo(tex_ficticio(idioma), inventario_ficticio()).aprovado


def test_todas_as_violacoes_aparecem_juntas(tmp_path):
    pdf = gravar_pdf(tmp_path, ["um", "dois"])
    tex = tex_com_corpo("\\input{x} \\tech{Cobol} feito \u2014 pronto a\u200bb")

    resultado = validar_curriculo(tex, inventario_ficticio(), pdf=pdf)

    assert set(resultado.regras) == {
        Regra.PAGINAS,
        Regra.LATEX,
        Regra.TECNOLOGIA,
        Regra.TRAVESSAO,
        Regra.CARACTERE_INVISIVEL,
    }
    assert not resultado.aprovado


def test_exigir_valido_levanta_com_as_regras_violadas():
    with pytest.raises(CurriculoInvalido) as erro:
        exigir_valido(tex_com_corpo("\\write18{x}"), inventario_ficticio())

    assert erro.value.resultado.regras == (Regra.LATEX,)
    assert "latex" in str(erro.value)


def test_exigir_valido_nao_levanta_para_curriculo_limpo():
    exigir_valido(tex_ficticio(), inventario_ficticio())


def test_pdf_de_duas_paginas_barra_mesmo_com_tex_limpo(tmp_path):
    pdf = gravar_pdf(tmp_path, ["um", "dois"])

    with pytest.raises(CurriculoInvalido):
        exigir_valido(tex_ficticio(), inventario_ficticio(), pdf=pdf)
