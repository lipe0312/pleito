from __future__ import annotations

from viabilidade.config import carregar
from viabilidade.triagem import (
    LIMITE_ANOS_EXPERIENCIA,
    LIMITE_DESCRICAO_UTIL,
    LIMITE_TEXTO_ANOS,
    LIMITE_TEXTO_FUNCAO,
    SIGLAS_FUNCAO,
    TERMOS_FORA,
    TERMOS_FUNCAO,
    TERMOS_GENERICOS,
)


def test_vocabulario_de_triagem_esta_em_config():
    config = carregar("triagem")
    assert config["termos_funcao"] == {
        funcao.value: list(termos) for funcao, termos in TERMOS_FUNCAO.items()
    }
    assert config["termos_fora"] == list(TERMOS_FORA)
    assert config["siglas_funcao"] == {
        funcao.value: list(siglas) for funcao, siglas in SIGLAS_FUNCAO.items()
    }
    assert set(config["termos_genericos"]) == TERMOS_GENERICOS


def test_limites_da_triagem_estao_em_config():
    limites = carregar("triagem")["limites"]
    assert limites["descricao_util_min_chars"] == LIMITE_DESCRICAO_UTIL
    assert limites["descricao_funcao_max_chars"] == LIMITE_TEXTO_FUNCAO
    assert limites["descricao_anos_max_chars"] == LIMITE_TEXTO_ANOS
    assert limites["anos_experiencia_max_detectavel"] == LIMITE_ANOS_EXPERIENCIA


def test_triagem_carrega_termos_sem_alterar_classificacao():
    from viabilidade.triagem import inferir_funcao

    assert inferir_funcao("Estagio em Analise de Dados").value == "dados"
    assert inferir_funcao(
        "Estagiario(a) de Servicos", "Trataremos seus dados pessoais conforme a LGPD"
    ).value == "indefinida"
    assert inferir_funcao("Analista de BI Junior").value == "dados"
