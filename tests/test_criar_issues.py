from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "scripts" / "next-task-full"


def carregar_modulo():
    sys.path.insert(0, str(PASTA))
    spec = importlib.util.spec_from_file_location("criar_issues", PASTA / "criar_issues.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


criar_issues = carregar_modulo()

ITEM = {
    "id": "F9.9",
    "fase": 9,
    "titulo": "Item ficticio",
    "zona": "ficticia",
    "depende": [],
    "schema": False,
    "toca": ["regra"],
    "modelo": "sonnet-high",
    "problema": "nada separa o alerta do resto.",
    "solucao": ["ler a config", "decidir em ordem"],
    "ve": "so vaga de verdade",
    "criterios": ["regra com teste"],
    "testes": ["fixture de convite nao vira vaga"],
    "docs": {"ler": ["docs/a.md"], "atualizar": ["docs/b.md"]},
    "riscos": "email e texto nao confiavel",
}
FASES = {9: {"objetivo": "objetivo ficticio", "ve": "fase"}}


def test_corpo_renderiza_problema_solucao_testes_docs_e_riscos():
    corpo = criar_issues.corpo_item(ITEM, FASES, {"F9.9": ITEM}, {})
    for trecho in (
        "## Problema\nNada separa o alerta do resto.\n",
        "## Como vamos resolver\n1. ler a config\n2. decidir em ordem\n",
        "## Testes que provam\n- fixture de convite nao vira vaga\n",
        "**Ler antes:**\n- docs/a.md\n",
        "**Atualizar no PR:**\n- docs/b.md\n",
        "## Riscos e cuidados\nEmail e texto nao confiavel.\n",
        "backlog: F9.9",
    ):
        assert trecho in corpo


def test_corpo_sem_detalhe_omite_as_secoes_novas():
    detalhe = {"problema", "solucao", "testes", "docs", "riscos"}
    minimo = {k: v for k, v in ITEM.items() if k not in detalhe}
    corpo = criar_issues.corpo_item(minimo, FASES, {"F9.9": minimo}, {})
    assert "## Problema" not in corpo and "## Documentação" not in corpo
