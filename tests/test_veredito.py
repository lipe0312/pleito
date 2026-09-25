from __future__ import annotations

from viabilidade.contratos import ResultadoColeta, Veredito
from viabilidade.veredito import Consolidado


def test_sem_ingest_util_e_no_go():
    c = Consolidado()
    c.ingest["gupy"] = Veredito.NO_GO
    assert c.global_ is Veredito.NO_GO


def test_ingest_ok_sem_egress_fica_nao_testado():
    c = Consolidado()
    c.ingest["greenhouse"] = Veredito.GO
    assert c.global_ is Veredito.NAO_TESTADO


def test_egress_no_go_derruba_tudo():
    c = Consolidado()
    c.ingest["greenhouse"] = Veredito.GO
    c.egress["gupy"] = Veredito.NO_GO
    c.baseline["pt"] = Veredito.GO
    assert c.global_ is Veredito.NO_GO


def test_baseline_ausente_derruba_tudo():
    c = Consolidado()
    c.ingest["greenhouse"] = Veredito.GO
    c.egress["gupy"] = Veredito.GO
    assert c.global_ is Veredito.NO_GO


def test_global_e_o_pior_dos_tres_quando_todos_passam():
    c = Consolidado()
    c.ingest["greenhouse"] = Veredito.GO
    c.egress["gupy"] = Veredito.GO_COM_RESSALVA
    c.baseline["pt"] = Veredito.GO
    c.baseline["en"] = Veredito.GO
    assert c.global_ is Veredito.GO_COM_RESSALVA


def test_registrar_coleta_guarda_evidencia():
    c = Consolidado()
    r = ResultadoColeta(fonte="ashby", robots_permite=True, http_status=200)
    r.evidencia["ramp"] = 7
    c.registrar_coleta(r)
    assert c.ingest["ashby"] is Veredito.NO_GO
    assert c.detalhes["ingest.ashby"]["evidencia"]["ramp"] == 7


def test_markdown_tem_veredito_global():
    c = Consolidado()
    c.ingest["greenhouse"] = Veredito.GO
    assert "Veredito global" in c.markdown()
