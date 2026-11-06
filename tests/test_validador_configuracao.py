from __future__ import annotations

import pytest
from apoio_validador import configuracao_com
from pydantic import ValidationError

from src.padroes.configuracao import configuracao_padroes
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


def test_configuracao_do_conteudo_carrega_com_secoes_por_idioma():
    config = configuracao_validador()

    assert config.conteudo.projetos.minimo == 3
    assert (
        list(config.conteudo.secoes["pt"].model_dump().values())
        == configuracao_padroes().ordem_secoes
    )
    assert set(config.conteudo.secoes) == set(configuracao_padroes().idiomas)


def test_idiomas_do_conteudo_precisam_ser_os_mesmos_em_tudo():
    with pytest.raises(ValidationError):
        configuracao_com(
            conteudo__secoes={
                "pt": {"sobre": "S", "formacao": "F", "experiencia": "E", "projetos": "P"}
            }
        )


def test_regex_de_parametro_livre_precisa_compilar():
    with pytest.raises(ValidationError):
        configuracao_com(conteudo__preambulo__parametros_livres=["("])


def test_minimo_de_projetos_nao_passa_do_maximo():
    with pytest.raises(ValidationError):
        configuracao_com(conteudo__projetos__minimo=5, conteudo__projetos__maximo=4)
