from __future__ import annotations

from pathlib import Path

import yaml

CAMINHO = Path(__file__).resolve().parents[1] / ".github" / "dependabot.yml"


def atualizacoes():
    dados = yaml.safe_load(CAMINHO.read_text(encoding="utf-8"))
    return dados["updates"]


def test_arquivo_usa_versao_2_do_dependabot():
    dados = yaml.safe_load(CAMINHO.read_text(encoding="utf-8"))
    assert dados["version"] == 2


def test_so_ecossistema_pip():
    ecossistemas = [item["package-ecosystem"] for item in atualizacoes()]
    assert ecossistemas == ["pip"]


def test_intervalo_semanal():
    intervalos = [item["schedule"]["interval"] for item in atualizacoes()]
    assert intervalos == ["weekly"]


def test_limite_de_prs_abertos_baixo_e_presente():
    limites = [item.get("open-pull-requests-limit") for item in atualizacoes()]
    assert len(limites) == 1
    assert isinstance(limites[0], int)
    assert 1 <= limites[0] <= 10
