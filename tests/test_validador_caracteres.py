from __future__ import annotations

import pytest
from apoio_validador import (
    configuracao_com,
    gravar_pdf,
    inventario_ficticio,
    tex_com_corpo,
    tex_ficticio,
)

from src.validador.caracteres import validar_invisiveis, validar_travessao
from src.validador.configuracao import configuracao_validador
from src.validador.resultado import Regra
from src.validador.validar import validar_curriculo

TRAVESSOES = {
    "em_dash": "feito \u2014 pronto",
    "tres_hifens": "feito --- pronto",
    "quatro_hifens": "feito ---- pronto",
    "barra_horizontal": "feito \u2015 pronto",
    "dois_pontos_travessao": "feito \u2e3a pronto",
    "travessao_triplo": "feito \u2e3b pronto",
    "travessao_pequeno": "feito \ufe58 pronto",
    "sem_espacos": "feito\u2014pronto",
}


def _regras(texto: str, funcao=validar_travessao) -> list[Regra]:
    return [v.regra for v in funcao(texto, configuracao_validador())]


@pytest.mark.parametrize("texto", TRAVESSOES.values(), ids=TRAVESSOES.keys())
def test_travessao_e_recusado(texto):
    assert _regras(texto) == [Regra.TRAVESSAO]


@pytest.mark.parametrize("texto", TRAVESSOES.values(), ids=TRAVESSOES.keys())
def test_travessao_dentro_do_curriculo_e_recusado(texto):
    resultado = validar_curriculo(tex_com_corpo(texto), inventario_ficticio())

    assert Regra.TRAVESSAO in resultado.regras


def test_faixa_com_dois_hifens_continua_valendo():
    assert _regras("2020 -- 2024") == []
    assert validar_curriculo(tex_ficticio(), inventario_ficticio()).aprovado


def test_travessao_no_texto_do_pdf_e_recusado(tmp_path):
    pdf = gravar_pdf(tmp_path, ["feito \u2014 pronto"])

    resultado = validar_curriculo(tex_ficticio(), inventario_ficticio(), pdf=pdf)

    assert Regra.TRAVESSAO in resultado.regras


def test_caracteres_proibidos_vem_da_configuracao():
    config = configuracao_com(caracteres__proibidos=[], caracteres__sequencias_proibidas=[])

    assert [v.regra for v in validar_travessao("a \u2014 b --- c", config)] == []


@pytest.mark.parametrize(
    "caractere",
    ["\u200b", "\u202e", "\u2028", "\ufeff", "\ue000", "\x00", "\x1b", "\u2066"],
    ids=["largura_zero", "direcao", "separador", "marca", "privado", "nulo", "escape", "isolado"],
)
def test_caractere_invisivel_ou_de_controle_e_recusado(caractere):
    assert _regras(f"Kuber{caractere}netes", validar_invisiveis) == [Regra.CARACTERE_INVISIVEL]


def test_quebra_de_linha_e_tabulacao_continuam_validas():
    assert _regras("linha\r\nnova\ttab", validar_invisiveis) == []


def test_curriculo_com_caractere_invisivel_e_recusado():
    resultado = validar_curriculo(tex_com_corpo("a\u200bb"), inventario_ficticio())

    assert Regra.CARACTERE_INVISIVEL in resultado.regras
