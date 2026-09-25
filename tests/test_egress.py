from __future__ import annotations

from pathlib import Path

import pytest

from viabilidade.contratos import MotivoNoGo, Veredito
from viabilidade.egress.fluxo import EtapaEgress, ResultadoEgress, executar_fluxo
from viabilidade.egress.navegador import (
    CampoProibido,
    SubmitBloqueado,
    exigir_campo_seguro,
    exigir_submit_autorizado,
)


@pytest.mark.parametrize(
    "seletor",
    [
        "input[name=password]",
        "#senha",
        "input[name=cpf]",
        "input[name=credit_card]",
        "#cartao-numero",
    ],
)
def test_campos_sensiveis_sao_bloqueados(seletor):
    with pytest.raises(CampoProibido):
        exigir_campo_seguro(seletor)


def test_campo_comum_passa():
    exigir_campo_seguro("input[name=linkedin_url]")


def test_submit_real_sem_token_e_bloqueado(monkeypatch):
    from viabilidade import config

    monkeypatch.setenv("PLEITO_EGRESS_MODO", "submit_real")
    monkeypatch.setenv("PLEITO_EGRESS_TOKEN_SUBMIT_REAL", "curto")
    config.ambiente.cache_clear()
    with pytest.raises(SubmitBloqueado):
        exigir_submit_autorizado()
    config.ambiente.cache_clear()


def test_submit_real_com_token_longo_passa(monkeypatch):
    from viabilidade import config

    monkeypatch.setenv("PLEITO_EGRESS_MODO", "submit_real")
    monkeypatch.setenv("PLEITO_EGRESS_TOKEN_SUBMIT_REAL", "a" * 32)
    config.ambiente.cache_clear()
    exigir_submit_autorizado()
    config.ambiente.cache_clear()


def test_dry_run_nunca_e_go_pleno():
    r = ResultadoEgress(url="https://x.com/vaga", modo="dry_run")
    for etapa in (
        EtapaEgress.ABRIR,
        EtapaEgress.SEM_CAPTCHA_VISIVEL,
        EtapaEgress.SEM_MURO_DE_LOGIN,
        EtapaEgress.ACHAR_FORMULARIO,
        EtapaEgress.ACHAR_ANEXO,
        EtapaEgress.ANEXAR_PDF,
        EtapaEgress.ACHAR_SUBMIT,
    ):
        r.marcar(etapa, True)
    assert r.veredito() is Veredito.GO_COM_RESSALVA


def test_submit_sem_confirmacao_e_no_go():
    r = ResultadoEgress(url="https://x.com/vaga", modo="submit_real")
    for etapa in (
        EtapaEgress.ABRIR,
        EtapaEgress.SEM_CAPTCHA_VISIVEL,
        EtapaEgress.SEM_MURO_DE_LOGIN,
        EtapaEgress.ACHAR_FORMULARIO,
        EtapaEgress.ACHAR_ANEXO,
        EtapaEgress.ANEXAR_PDF,
        EtapaEgress.ACHAR_SUBMIT,
        EtapaEgress.SUBMETER,
    ):
        r.marcar(etapa, True)
    r.marcar(EtapaEgress.DETECTAR_CONFIRMACAO, False)
    r.motivos.append(MotivoNoGo.SEM_PROVA_ENVIO)
    assert r.veredito() is Veredito.NO_GO


def test_submit_com_confirmacao_e_go():
    r = ResultadoEgress(url="https://x.com/vaga", modo="submit_real")
    for etapa in EtapaEgress:
        r.marcar(etapa, True)
    r.marcar(EtapaEgress.DETECTAR_CAPTCHA, False)
    assert r.veredito() is Veredito.GO


def test_muro_de_login_derruba_veredito():
    r = ResultadoEgress(url="https://x.com/vaga", modo="dry_run")
    for etapa in EtapaEgress:
        r.marcar(etapa, True)
    r.marcar(EtapaEgress.SEM_MURO_DE_LOGIN, False)
    r.motivos.append(MotivoNoGo.EXIGE_LOGIN)
    assert r.veredito() is Veredito.NO_GO


def test_captcha_derruba_veredito():
    r = ResultadoEgress(url="https://x.com/vaga", modo="dry_run")
    r.motivos.append(MotivoNoGo.CAPTCHA)
    assert r.veredito() is Veredito.NO_GO


def test_asset_estatico_de_terceiro_e_liberado():
    from viabilidade.egress.navegador import TIPOS_ESTATICOS, TIPOS_NAVEGACAO

    assert "script" in TIPOS_ESTATICOS
    assert "stylesheet" in TIPOS_ESTATICOS
    assert "font" in TIPOS_ESTATICOS
    assert TIPOS_ESTATICOS.isdisjoint(TIPOS_NAVEGACAO)


def test_navegacao_e_xhr_continuam_restritos():
    from viabilidade.egress.navegador import TIPOS_NAVEGACAO

    for tipo in ("document", "xhr", "fetch", "websocket"):
        assert tipo in TIPOS_NAVEGACAO


def test_pdf_inexistente_falha_antes_de_abrir_navegador():
    r = executar_fluxo("https://x.com/vaga", Path("/nao/existe.pdf"), respostas={})
    assert r.erro is not None
    assert r.etapas == {}
