from __future__ import annotations

import json
from pathlib import Path

CAMINHO = Path(__file__).resolve().parents[1] / "docs" / "protecao-main.json"


def protecao():
    return json.loads(CAMINHO.read_text(encoding="utf-8"))


def test_nao_permite_force_push():
    assert protecao()["allow_force_pushes"] is False


def test_nao_permite_exclusao_da_main():
    assert protecao()["allow_deletions"] is False


def test_exige_historico_linear():
    assert protecao()["required_linear_history"] is True


def test_nao_exige_aprovacao_para_o_squash_do_fluxo():
    revisoes = protecao()["required_pull_request_reviews"]
    assert revisoes["required_approving_review_count"] == 0


def test_exige_pull_request_para_entrar_na_main():
    assert isinstance(protecao()["required_pull_request_reviews"], dict)


def test_vale_tambem_para_o_dono():
    assert protecao()["enforce_admins"] is True
