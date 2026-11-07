from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import carregar
from src.padroes.configuracao import PASTA_DOS_PROMPTS
from src.triagem import configuracao
from src.triagem.configuracao import Eliminatorios, PontuacaoFinal


def _pontuacao_final(**campos) -> dict:
    return {**carregar("triagem")["pontuacao_final"], **campos}


def test_padrao_de_injecao_invalido_quebra_ao_carregar_o_config():
    with pytest.raises(ValidationError, match="padrao de injecao invalido"):
        PontuacaoFinal.model_validate(_pontuacao_final(padroes_injecao=["(aberto"]))


def test_padroes_de_injecao_do_config_compilam():
    PontuacaoFinal.model_validate(_pontuacao_final())


@pytest.mark.parametrize("dias", [0, -1])
def test_idade_maxima_precisa_ser_positiva(dias):
    bruto = {**carregar("filtros")["eliminatorios"], "idade_maxima_dias": dias}
    with pytest.raises(ValidationError):
        Eliminatorios.model_validate(bruto)


def test_pasta_dos_prompts_e_a_mesma_do_modulo_de_padroes():
    assert configuracao.PASTA_DOS_PROMPTS is PASTA_DOS_PROMPTS


def test_prompt_fora_da_pasta_e_recusado():
    with pytest.raises(ValidationError):
        PontuacaoFinal.model_validate(_pontuacao_final(prompt="config/pontuar_vaga.md"))
