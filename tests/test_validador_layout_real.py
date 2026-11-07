from __future__ import annotations

import shutil

import pytest
from apoio_validador import contexto_rico, inventario_rico, tex_rico

from src.gerador.compilar import CompilacaoFalhou, compilar
from src.gerador.configuracao import configuracao_gerador
from src.validador import layout
from src.validador.paginas import texto_do_pdf
from src.validador.validar import validar_curriculo

pytestmark = pytest.mark.latex

CODIGOS_DE_LAYOUT = {"V1", "V3", "V4", "V5", "V18"}


@pytest.fixture
def compilador(tmp_path):
    config = configuracao_gerador()
    if shutil.which(config.compilacao.motor) is None:
        pytest.skip(f"{config.compilacao.motor} nao instalado")

    def compilar_tex(tex):
        pdf = compilar(tex, tmp_path, config)
        return pdf, pdf.with_suffix(".log")

    return compilar_tex


def achados(tex, pdf, log, idioma="pt"):
    resultado = validar_curriculo(
        tex, inventario_rico(), None, pdf, log=log, contexto=contexto_rico(idioma)
    )
    return [v for v in resultado.violacoes if v.codigo in CODIGOS_DE_LAYOUT]


def sem_regra(monkeypatch, codigo):
    restantes = tuple(
        funcao for funcao in layout.REGRAS_DE_LAYOUT if funcao.__name__ != DESLIGAVEIS[codigo]
    )
    assert len(restantes) == len(layout.REGRAS_DE_LAYOUT) - 1
    monkeypatch.setattr(layout, "REGRAS_DE_LAYOUT", restantes)


DESLIGAVEIS = {
    "V1": "validar_compilacao",
    "V3": "validar_caixas",
    "V4": "validar_titulo_e_data",
    "V5": "validar_sobreposicao",
    "V18": "validar_limites",
}


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_template_real_compilado_passa_no_layout(compilador, idioma):
    tex = tex_rico(idioma)
    pdf, log = compilador(tex)

    assert achados(tex, pdf, log, idioma) == []
    assert "Python" in texto_do_pdf(pdf)


def test_hbox_estourada_real_e_recusada_por_v3(compilador, monkeypatch):
    tex = tex_rico().replace(
        "Mantive filas com", "Mantive filas com " + "Supercalifragilistico" * 6 + " e"
    )
    pdf, log = compilador(tex)

    assert "Overfull" in log.read_text(encoding="utf-8", errors="replace")
    assert "V3" in {v.codigo for v in achados(tex, pdf, log)}
    sem_regra(monkeypatch, "V3")
    assert "V3" not in {v.codigo for v in achados(tex, pdf, log)}


def test_titulo_longo_que_empurra_a_data_e_recusado_por_v4(compilador, monkeypatch):
    tex = tex_rico().replace(
        "Desenvolvedora Estagiária",
        "Desenvolvedora Estagiária Responsavel Por Muitos Sistemas Internos De Dados Distribuidos",
    )
    pdf, log = compilador(tex)

    assert "V4" in {v.codigo for v in achados(tex, pdf, log)}
    sem_regra(monkeypatch, "V4")
    assert "V4" not in {v.codigo for v in achados(tex, pdf, log)}


def test_linespread_abaixo_do_minimo_compilado_e_recusado_por_v18(compilador, monkeypatch):
    tex = tex_rico().replace(
        "\\setlength{\\parindent}{0pt}", "\\linespread{0.80}\n\\setlength{\\parindent}{0pt}"
    )
    pdf, log = compilador(tex)

    assert "V18" in {v.codigo for v in achados(tex, pdf, log)}
    sem_regra(monkeypatch, "V18")
    assert "V18" not in {v.codigo for v in achados(tex, pdf, log)}


def test_linhas_que_se_sobrepoem_no_pdf_real_sao_recusadas_por_v5(compilador, monkeypatch):
    tex = tex_rico().replace("\\vspace{2mm}", "\\vspace{-6mm}", 1)
    pdf, log = compilador(tex)

    assert "V5" in {v.codigo for v in achados(tex, pdf, log)}
    sem_regra(monkeypatch, "V5")
    assert "V5" not in {v.codigo for v in achados(tex, pdf, log)}


def test_erro_do_pdflatex_real_vira_v1_com_as_linhas_do_log(tmp_path):
    config = configuracao_gerador()
    if shutil.which(config.compilacao.motor) is None:
        pytest.skip(f"{config.compilacao.motor} nao instalado")
    tex = tex_rico().replace("Mantive filas com", "\\comandoinexistente Mantive filas com")
    with pytest.raises(CompilacaoFalhou):
        compilar(tex, tmp_path, config)

    resultado = validar_curriculo(
        tex, inventario_rico(), None, None, log=tmp_path / "cv.log", contexto=contexto_rico()
    )
    v1 = [v for v in resultado.violacoes if v.codigo == "V1"]

    assert v1
    assert "Undefined control sequence" in v1[0].detalhe
