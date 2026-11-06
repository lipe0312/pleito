from __future__ import annotations

import shutil

import pytest
from apoio_gerador import ATAQUES, conteudo_ficticio, slots_ficticios, travado_ficticio
from pypdf import PdfReader

from src.gerador.compilar import CompilacaoFalhou, PaginasDemais, compilar
from src.gerador.configuracao import configuracao_gerador
from src.gerador.renderizar import renderizar

pytestmark = pytest.mark.latex


@pytest.fixture(scope="module")
def config():
    configuracao = configuracao_gerador()
    if shutil.which(configuracao.compilacao.motor) is None:
        pytest.skip(f"{configuracao.compilacao.motor} nao instalado")
    return configuracao


@pytest.fixture(scope="module")
def conteudo():
    return conteudo_ficticio()


def _texto(pdf) -> str:
    return " ".join(pagina.extract_text() for pagina in PdfReader(pdf).pages)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_fixture_ficticia_compila_em_uma_pagina(conteudo, config, tmp_path, idioma):
    blocos, inventario = conteudo
    tex = renderizar(
        idioma, slots_ficticios(blocos, idioma), travado_ficticio(), blocos, inventario, config
    )

    pdf = compilar(tex, tmp_path, config)

    assert len(PdfReader(pdf).pages) == 1
    texto = _texto(pdf)
    assert "PESSOA FICTICIA" in texto
    assert "Python" in texto


def test_pdf_com_ataque_em_todos_os_slots_compila_como_texto_inerte(conteudo, config, tmp_path):
    blocos, inventario = conteudo
    ataque = " ".join(ATAQUES)[:250]
    slots = slots_ficticios(blocos, "pt")
    slots["sobre"] = {"texto": ataque, "techs": []}
    slots["disciplinas"] = [ataque[:60], ataque[60:120]]
    for entrada in slots["experiencias"] + slots["projetos"]:
        entrada["bullets"] = [{"texto": ataque, "techs": []}]
    tex = renderizar("pt", slots, travado_ficticio(), blocos, inventario, config)

    pdf = compilar(tex, tmp_path, config)

    assert len(PdfReader(pdf).pages) == 1
    assert "root:" not in _texto(pdf)


def test_shell_escape_fica_desligado(config, tmp_path):
    marcador = tmp_path / "executou_shell"
    tex = (
        "\\documentclass{article}\\begin{document}"
        f"\\immediate\\write18{{touch {marcador}}}ok\\end{{document}}"
    )

    compilar(tex, tmp_path / "trabalho", config)

    assert not marcador.exists()


def test_leitura_de_arquivo_fora_da_pasta_e_recusada(config, tmp_path):
    tex = "\\documentclass{article}\\begin{document}\\input{/etc/hosts}\\end{document}"

    with pytest.raises(CompilacaoFalhou):
        compilar(tex, tmp_path, config)


def test_documento_de_duas_paginas_e_recusado(config, tmp_path):
    tex = "\\documentclass{article}\\begin{document}a\\newpage b\\end{document}"

    with pytest.raises(PaginasDemais):
        compilar(tex, tmp_path, config)
