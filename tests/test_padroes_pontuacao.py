from __future__ import annotations

import pytest

from src.padroes.configuracao import configuracao_padroes
from src.padroes.pontuacao import violacoes_de_pontuacao

BOM = "Modelei o domínio de pedidos; implementei as regras de cobrança com Python."


def test_bullet_com_ponto_final_e_ponto_e_virgula_passa():
    assert violacoes_de_pontuacao(configuracao_padroes(), BOM) == []


def test_bullet_sem_ponto_final_e_recusado():
    assert violacoes_de_pontuacao(configuracao_padroes(), BOM.rstrip(".")) == ["terminador"]


@pytest.mark.parametrize("caractere", configuracao_padroes().pontuacao.proibidos)
def test_cada_travessao_proibido_e_recusado(caractere):
    texto = BOM.replace(";", f" {caractere}")
    assert violacoes_de_pontuacao(configuracao_padroes(), texto) == [f"proibido {caractere}"]
