from __future__ import annotations

import re

import pytest
from apoio_gerador import ATAQUES, COMANDOS_DE_ESCAPE, CONTROLES

from src.gerador.configuracao import configuracao_gerador
from src.gerador.erros import SlotInvalido, TechForaDoInventario
from src.gerador.escape import LatexSeguro, compor_texto, escapar_latex, texto_limpo, url_segura

SEQUENCIAS_INOFENSIVAS = re.compile(
    r"\\text(?:backslash|asciicircum|asciitilde|quotedbl|less|greater|bar|asciigrave)\{\}"
    r"|\{[\[\]]\}"
    r"|\\[{}$&%#_]"
)
ESPECIAIS_CRUS = re.compile(r"[\\{}$&%#_^~\[\]]")


@pytest.fixture(scope="module")
def config():
    return configuracao_gerador()


@pytest.mark.parametrize("ataque", ATAQUES)
def test_escape_deixa_so_sequencias_inofensivas(ataque):
    escapado = escapar_latex(ataque)

    restante = SEQUENCIAS_INOFENSIVAS.sub("", escapado)

    assert not ESPECIAIS_CRUS.search(restante)
    assert "^^" not in escapado
    assert not re.search(r"\\(?:input|include|write|immediate|openin|catcode|def|csname)", escapado)


def test_escape_dos_dez_especiais_do_plano():
    assert escapar_latex("\\") == r"\textbackslash{}"
    assert escapar_latex("{}") == r"\{\}"
    assert escapar_latex("$&%#_") == r"\$\&\%\#\_"
    assert escapar_latex("^") == r"\textasciicircum{}"
    assert escapar_latex("~") == r"\textasciitilde{}"


def test_escape_de_colchetes_impede_argumento_opcional_e_fechamento_solto():
    assert escapar_latex("[Python]") == "{[}Python{]}"
    assert escapar_latex("]") == "{]}"


def test_escape_mantem_acento_e_pontuacao_comum():
    assert escapar_latex("Visão em tempo real, 2023 -- hoje (ok).") == (
        "Visão em tempo real, 2023 -- hoje (ok)."
    )


def test_escape_nao_dobra_barra_ja_escapada():
    assert escapar_latex(r"\%") == r"\textbackslash{}\%"


@pytest.mark.parametrize("controle", CONTROLES)
def test_texto_limpo_recusa_quebra_de_linha_e_unicode_de_controle(controle):
    with pytest.raises(SlotInvalido):
        texto_limpo(controle, 100, "teste")


@pytest.mark.parametrize("valor", ["", "   ", 5, None, ["x"], b"x"])
def test_texto_limpo_recusa_vazio_e_tipo_errado(valor):
    with pytest.raises(SlotInvalido):
        texto_limpo(valor, 100, "teste")


def test_texto_limpo_recusa_acima_do_limite_e_aceita_no_limite():
    assert texto_limpo("a" * 10, 10, "teste") == "a" * 10
    with pytest.raises(SlotInvalido):
        texto_limpo("a" * 11, 10, "teste")


def test_texto_limpo_apara_bordas():
    assert texto_limpo("  Olá  ", 10, "teste") == "Olá"


@pytest.mark.parametrize(
    "url",
    [
        "https://exemplo.invalid/a b",
        "https://exemplo.invalid/a}{\\input{x}",
        "https://exemplo.invalid/a%20b",
        "https://exemplo.invalid/a#b",
        "https://exemplo.invalid/~a",
        "https://exemplo.invalid/a_b^c",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://exemplo.invalid",
        "https://exemplo.invalid/\n",
        "",
    ],
)
def test_url_segura_recusa_o_que_exigiria_escape(url, config):
    with pytest.raises(SlotInvalido):
        url_segura(url, config.travado.padrao_url, "link")


def test_url_segura_aceita_https_e_mailto(config):
    assert url_segura("https://exemplo.invalid/alfa", config.travado.padrao_url, "l")
    assert url_segura("mailto:pessoa@exemplo.invalid", config.travado.padrao_url, "l")


def test_compor_texto_marca_so_a_tech_pedida_e_escapa_o_resto():
    resultado = compor_texto("Usei Python e Flask em 100% dos casos", ["Python"], {"Python"})

    assert isinstance(resultado, LatexSeguro)
    assert resultado == r"Usei \tech{Python} e Flask em 100\% dos casos"


def test_compor_texto_prefere_a_tech_mais_longa_e_respeita_limite_de_palavra():
    texto = "Docker Compose e Docker, mas nao Dockerfile"

    resultado = compor_texto(texto, ["Docker", "Docker Compose"], {"Docker", "Docker Compose"})

    assert resultado == r"\tech{Docker Compose} e \tech{Docker}, mas nao Dockerfile"


def test_compor_texto_escapa_dentro_da_tech():
    resultado = compor_texto(
        "Reconhecimento com face_recognition", ["face_recognition"], {"face_recognition"}
    )

    assert resultado == r"Reconhecimento com \tech{face\_recognition}"


def test_compor_texto_recusa_tech_fora_do_inventario():
    with pytest.raises(TechForaDoInventario):
        compor_texto("Usei Kubernetes", ["Kubernetes"], {"Python"})


@pytest.mark.parametrize("ataque", ATAQUES)
def test_compor_texto_com_ataque_so_gera_o_comando_tech(ataque):
    resultado = compor_texto(f"Python {ataque}", ["Python"], {"Python"})

    comandos = set(re.findall(r"\\([A-Za-z]+)", resultado))
    assert comandos <= {"tech"} | COMANDOS_DE_ESCAPE
    fora_da_tech = resultado.replace(r"\tech{Python}", "")
    assert not ESPECIAIS_CRUS.search(SEQUENCIAS_INOFENSIVAS.sub("", fora_da_tech))
