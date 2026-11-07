from __future__ import annotations

from copy import deepcopy
from datetime import date

from src.avaliacao.liberacao import configuracao_em_avaliacao, tiers_habilitados_sem_aprovacao
from src.config import carregar


def test_nenhum_tier_habilitado_sem_avaliacao_aprovada_no_config():
    assert tiers_habilitados_sem_aprovacao(carregar("modelos")) == []


def test_habilitado_sem_status_aprovado_e_detectado():
    modelos = deepcopy(carregar("modelos"))
    modelos["tiers"]["rapido"]["habilitado"] = True

    assert tiers_habilitados_sem_aprovacao(modelos) == ["rapido"]


def test_aprovado_sem_conjunto_ou_data_tambem_e_detectado():
    modelos = deepcopy(carregar("modelos"))
    forte = modelos["tiers"]["forte"]
    forte["habilitado"] = True
    forte["avaliacao"] = {"status": "aprovado", "conjunto": "v1-abc", "data": None}

    assert tiers_habilitados_sem_aprovacao(modelos) == ["forte"]

    forte["avaliacao"]["data"] = "2026-11-06"
    assert tiers_habilitados_sem_aprovacao(modelos) == []


def test_configuracao_em_avaliacao_libera_so_o_tier_avaliado_e_nao_muda_o_original():
    original = carregar("modelos")
    antes = deepcopy(original)

    copia = configuracao_em_avaliacao(original, "forte", "v1-abc", date(2026, 11, 6))

    assert original == antes
    assert copia["tiers"]["forte"]["habilitado"] is True
    assert copia["tiers"]["forte"]["avaliacao"]["conjunto"] == "em_avaliacao:v1-abc"
    assert copia["tiers"]["rapido"]["habilitado"] is False
