from __future__ import annotations

import copy
import re

import pytest
from pydantic import ValidationError

from src.config import carregar
from src.gerador.configuracao import configuracao_gerador
from src.padroes.configuracao import configuracao_padroes


def _bruto() -> dict:
    return copy.deepcopy(carregar("padroes_curriculo"))


def test_yaml_real_valida_e_cobre_todos_os_idiomas_por_familia():
    config = configuracao_padroes()
    assert set(config.foco_sobre) >= {"backend_arquitetura", "dados_ml_ia"}
    for foco in config.foco_sobre.values():
        assert set(foco) == set(config.idiomas)


def test_pesos_da_rubrica_somam_um():
    config = configuracao_padroes()
    total = sum(criterio.peso for criterio in config.rubrica.criterios.values())
    assert round(total, 6) == 1


def test_pesos_que_nao_somam_um_sao_recusados():
    bruto = _bruto()
    bruto["rubrica"]["criterios"]["bullet_vago"]["peso"] = 0.5
    with pytest.raises(ValidationError, match="somar 1"):
        configuracao_padroes(bruto)


def test_criterio_da_rubrica_faltando_e_recusado():
    bruto = _bruto()
    del bruto["rubrica"]["criterios"]["sobre_generico"]
    with pytest.raises(ValidationError):
        configuracao_padroes(bruto)


def test_campo_desconhecido_e_recusado():
    bruto = _bruto()
    bruto["extra"] = 1
    with pytest.raises(ValidationError):
        configuracao_padroes(bruto)


def test_lista_por_idioma_sem_um_dos_idiomas_e_recusada():
    bruto = _bruto()
    del bruto["verbos_abertura_aceitos"]["en"]
    with pytest.raises(ValidationError, match="idiomas"):
        configuracao_padroes(bruto)


def test_faixa_invertida_e_recusada():
    bruto = _bruto()
    bruto["bullet"]["chars"] = {"minimo": 300, "maximo": 10}
    with pytest.raises(ValidationError):
        configuracao_padroes(bruto)


def test_nota_minima_fora_de_zero_a_um_e_recusada():
    bruto = _bruto()
    bruto["rubrica"]["nota_minima"] = 1.5
    with pytest.raises(ValidationError):
        configuracao_padroes(bruto)


def test_lista_de_regra_vazia_e_recusada():
    bruto = _bruto()
    bruto["nao_invencao"] = []
    with pytest.raises(ValidationError):
        configuracao_padroes(bruto)


def test_tamanhos_do_padrao_cabem_nos_slots_do_gerador():
    padroes = configuracao_padroes()
    slots = configuracao_gerador().slots
    assert padroes.bullet.chars.maximo <= slots["experiencias"].max_chars
    assert padroes.bullet.chars.maximo <= slots["projetos"].max_chars
    assert padroes.sobre.chars.maximo <= slots["sobre"].max_chars


def test_yaml_nao_carrega_dado_pessoal():
    texto = repr(carregar("padroes_curriculo"))
    assert not re.search(r"@|https?://|www\.|\d{8,}", texto)
