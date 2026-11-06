from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
MODELOS_VALIDOS = {"opus-high", "sonnet-high", "sonnet-medium", "haiku-medium"}


def carregar_modulo():
    caminho = RAIZ / "scripts" / "next-task-full" / "backlog.py"
    spec = importlib.util.spec_from_file_location("backlog_painel", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


backlog = carregar_modulo()


def item(zona: str, depende: list[str] | None = None, schema: bool = False, fase: int = 1):
    return {"zona": zona, "depende": depende or [], "schema": schema, "fase": fase}


def test_dependente_de_item_em_andamento_espera_a_onda_seguinte():
    itens = {"F1.1": item("a"), "F1.2": item("b", ["F1.1"])}
    plano = backlog.calcular_ondas(itens, set(), [backlog.Frente("F1.1", "a", False)], 3)
    assert "F1.2" not in plano.ondas[0]
    assert "F1.2" in plano.ondas[1]


def test_mesma_zona_nunca_fica_na_mesma_onda():
    itens = {"F1.1": item("painel"), "F1.2": item("painel"), "F1.3": item("email")}
    plano = backlog.calcular_ondas(itens, set(), [], 3)
    assert plano.ondas[0] == ["F1.1", "F1.3"]
    assert plano.ondas[1] == ["F1.2"]


def test_no_maximo_uma_migration_por_onda_contando_a_aberta():
    itens = {"F4.1": item("a", schema=True), "F5.1": item("b", schema=True), "F6.1": item("c")}
    aberta = [backlog.Frente("#40", "x", True)]
    plano = backlog.calcular_ondas(itens, set(), aberta, 3)
    assert plano.ondas[0] == ["F6.1"]
    assert plano.ondas[1] == ["F4.1"]
    assert plano.ondas[2] == ["F5.1"]


def test_frentes_ocupadas_reduzem_a_primeira_onda():
    itens = {"F1.1": item("a"), "F1.2": item("b"), "F1.3": item("c")}
    ocupadas = [backlog.Frente("#1", "x", False), backlog.Frente("#2", "y", False)]
    plano = backlog.calcular_ondas(itens, set(), ocupadas, 3)
    assert plano.ondas[0] == ["F1.1"]


def test_dependencia_de_manual_pendente_fica_sem_onda():
    itens = {"F8.1": item("calendar", ["M12"])}
    plano = backlog.calcular_ondas(itens, set(), [], 3)
    assert plano.sem_onda == {"F8.1": ["M12"]}


def test_issue_aberta_vence_a_fechada_com_o_mesmo_marcador():
    fechada = {"number": 2, "state": "closed", "state_reason": "completed", "body": "backlog: F1.1"}
    aberta = {"number": 9, "state": "open", "body": "x\n\nbacklog: F1.1"}
    por_id, _ = backlog.mapear_issues([fechada, aberta], {"F1.1"})
    assert por_id["F1.1"]["number"] == 9


def test_fechada_como_nao_planejada_nao_conta_como_concluida():
    feita = {"number": 3, "state": "closed", "state_reason": "completed", "body": "backlog: F1.1"}
    descartada = {
        "number": 7,
        "state": "closed",
        "state_reason": "not_planned",
        "body": "backlog: F1.1",
    }
    por_id, _ = backlog.mapear_issues([descartada, feita], {"F1.1"})
    assert por_id["F1.1"]["number"] == 3
    assert not backlog.concluida(descartada)


def test_marcador_desconhecido_vira_issue_avulsa():
    issue = {"number": 5, "state": "open", "body": "backlog: F99.9"}
    por_id, avulsas = backlog.mapear_issues([issue], {"F1.1"})
    assert por_id == {}
    assert avulsas == [issue]


def test_marcador_so_vale_em_linha_propria():
    assert backlog.marcador("texto backlog: F1.1") is None
    assert backlog.marcador("texto\nbacklog: F1.1\n") == "F1.1"


@pytest.fixture(scope="module")
def backlog_real():
    return backlog.carregar_backlog(RAIZ)


def test_backlog_real_sem_dependencia_inexistente(backlog_real):
    ids = {i["id"] for i in backlog_real["itens"]} | {m["id"] for m in backlog_real["manuais"]}
    faltando = [
        (registro["id"], dependencia)
        for registro in backlog_real["itens"] + backlog_real["manuais"]
        for dependencia in registro["depende"]
        if dependencia not in ids
    ]
    assert faltando == []


def test_backlog_real_sem_ciclo_e_com_campos_obrigatorios(backlog_real):
    itens = {i["id"]: i for i in backlog_real["itens"]}
    assert len(itens) == len(backlog_real["itens"])
    for registro in itens.values():
        assert registro["modelo"] in MODELOS_VALIDOS
        assert registro["criterios"]
        assert str(registro["fase"]) in {str(f) for f in backlog_real["fases"]}
    manuais = {m["id"] for m in backlog_real["manuais"]}
    plano = backlog.calcular_ondas(itens, manuais, [], 3)
    assert plano.sem_onda == {}
    assert sorted(i for onda in plano.ondas for i in onda) == sorted(itens)


def test_backlog_real_manual_diz_como_fazer_e_como_conferir(backlog_real):
    for manual in backlog_real["manuais"]:
        assert manual["id"].startswith("M")
        assert manual["titulo"] and manual["como"] and manual["pronto"] and manual["porque"]


def test_backlog_real_item_por_fazer_diz_problema_solucao_e_documentacao(backlog_real):
    concluidos = set(backlog_real["concluidos_antes_do_detalhamento"])
    sem_detalhe = [
        registro["id"]
        for registro in backlog_real["itens"]
        if registro["id"] not in concluidos
        and not (
            registro.get("problema")
            and registro.get("solucao")
            and registro.get("docs", {}).get("ler")
            and registro.get("docs", {}).get("atualizar")
        )
    ]
    assert sem_detalhe == []


def test_backlog_real_concluidos_existem(backlog_real):
    ids = {i["id"] for i in backlog_real["itens"]}
    assert set(backlog_real["concluidos_antes_do_detalhamento"]) <= ids
