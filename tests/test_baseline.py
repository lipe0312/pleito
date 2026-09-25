from __future__ import annotations

import shutil

import pytest

from viabilidade.baseline.extrair import GUIA, aplicar_correcoes, extrair_bases
from viabilidade.baseline.validar import checar_latex_perigoso, validar_tex
from viabilidade.contratos import Veredito


def test_corrige_underscore_em_tech():
    tex, aplicadas = aplicar_correcoes(r"\tech{face_recognition}")
    assert tex == r"\tech{face\_recognition}"
    assert aplicadas


def test_nao_duplica_escape_ja_correto():
    tex, aplicadas = aplicar_correcoes(r"\tech{face\_recognition}")
    assert tex == r"\tech{face\_recognition}"
    assert not aplicadas


def test_remove_markdown_antes_do_end_document():
    tex, aplicadas = aplicar_correcoes("texto\n## \\end{document}")
    assert tex.endswith("\\end{document}")
    assert "##" not in tex
    assert aplicadas


@pytest.mark.parametrize(
    "comando",
    [r"\write18{rm -rf /}", r"\input{|ls}", r"\openout1=x", r"\csname foo\endcsname"],
)
def test_latex_perigoso_e_detectado(comando):
    assert checar_latex_perigoso(f"\\documentclass{{article}}{comando}")


def test_latex_limpo_passa():
    assert checar_latex_perigoso(r"\documentclass{article}\begin{document}oi\end{document}") == []


def test_tex_perigoso_nunca_compila():
    r = validar_tex("pt", r"\documentclass{article}\write18{ls}\begin{document}x\end{document}")
    assert r.compilou is False
    assert r.veredito() is Veredito.NO_GO


@pytest.mark.skipif(not GUIA.exists(), reason="guia ausente")
def test_extrai_dois_curriculos_do_guia():
    bases = extrair_bases()
    assert set(bases) == {"pt", "en"}
    for registro in bases.values():
        assert registro["tex"].startswith("\\documentclass")
        assert registro["tex"].rstrip().endswith("\\end{document}")


@pytest.mark.skipif(not GUIA.exists(), reason="guia ausente")
def test_correcoes_necessarias_apenas_no_en():
    bases = extrair_bases()
    assert bases["en"]["correcoes"], "versao EN do guia deveria exigir correcao"


@pytest.mark.latex
@pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex ausente")
@pytest.mark.skipif(not GUIA.exists(), reason="guia ausente")
@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_baseline_compila_em_uma_pagina(idioma):
    bases = extrair_bases()
    r = validar_tex(idioma, bases[idioma]["tex"])
    assert r.compilou, r.log_erro
    assert r.paginas == 1
    assert r.veredito() in (Veredito.GO, Veredito.GO_COM_RESSALVA)
