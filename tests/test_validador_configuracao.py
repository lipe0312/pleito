from __future__ import annotations

import pytest
from apoio_validador import configuracao_com
from pydantic import ValidationError

from src.validador.configuracao import configuracao_validador


def test_configuracao_do_repositorio_carrega_com_limite_de_uma_pagina():
    config = configuracao_validador()

    assert config.paginas_max == 1
    assert "input" not in config.latex.corpo.comandos
    assert "\u2014" in config.caracteres.proibidos


def test_limite_de_paginas_precisa_ser_positivo():
    with pytest.raises(ValidationError):
        configuracao_com(paginas_max=0)


def test_chave_desconhecida_na_configuracao_e_recusada():
    with pytest.raises(ValidationError):
        configuracao_com(latex__corpo__comandos_extras=["input"])


def test_simbolo_de_controle_precisa_ter_um_caractere():
    with pytest.raises(ValidationError):
        configuracao_com(latex__corpo__simbolos=["ab"])
