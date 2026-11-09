from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from src.coletor import conformidade
from src.coletor.base import ColetorHttp
from src.coletor.conformidade import (
    TermosNaoPermitem,
    dominios_permitidos,
    exigir_termos_permitidos,
)
from src.coletor.contratos import MotivoNoGo
from src.config import carregar

RAIZ = Path(__file__).resolve().parent.parent
URL = "https://fonte-ficticia.example.net/vagas"
VEREDITOS_COLETAVEIS = ["permite", "permite_com_condicao"]


def _config(**fonte) -> dict:
    return {
        "vereditos_coletaveis": VEREDITOS_COLETAVEIS,
        "fontes": {"ficticia": {"dominios": ["fonte-ficticia.example.net"], **fonte}},
    }


def _termos(veredito: str, revisado_em: str | None = "2026-11-07") -> dict:
    termos = {"veredito": veredito, "link": "https://fonte-ficticia.example.net/termos"}
    if revisado_em is not None:
        termos["revisado_em"] = revisado_em
    return {"termos": termos}


class FonteFicticia(ColetorHttp):
    slug = "ficticia"
    verificar_robots = False

    def _executar(self, resultado, limite):
        resultado.http_status = self._buscar(URL).status_code


@pytest.fixture
def coletor():
    cliente = httpx.Client()
    c = FonteFicticia(client=cliente)
    c._limitador = conformidade.Limitador(0)
    yield c
    cliente.close()


def _coletar(monkeypatch, coletor, config: dict):
    monkeypatch.setattr(conformidade, "carregar", lambda nome: config)
    with respx.mock(assert_all_called=False) as mock:
        rota = mock.get(URL).respond(200, json={})
        resultado = coletor.coletar(5)
    return resultado, rota.call_count


def test_fonte_sem_termos_nao_e_coletada(monkeypatch, coletor):
    resultado, chamadas = _coletar(monkeypatch, coletor, _config())
    assert chamadas == 0
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos
    assert resultado.erro


def test_fonte_com_veredito_proibe_nao_e_coletada(monkeypatch, coletor):
    resultado, chamadas = _coletar(monkeypatch, coletor, _config(**_termos("proibe")))
    assert chamadas == 0
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos


def test_fonte_com_veredito_permite_e_coletada(monkeypatch, coletor):
    resultado, chamadas = _coletar(monkeypatch, coletor, _config(**_termos("permite")))
    assert chamadas == 1
    assert resultado.erro is None
    assert resultado.http_status == 200


def test_fonte_com_condicao_e_coletada(monkeypatch, coletor):
    resultado, chamadas = _coletar(
        monkeypatch, coletor, _config(**_termos("permite_com_condicao"))
    )
    assert chamadas == 1


def test_revisado_em_ausente_recusa(monkeypatch, coletor):
    resultado, chamadas = _coletar(
        monkeypatch, coletor, _config(**_termos("permite", revisado_em=None))
    )
    assert chamadas == 0
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos


def test_veredito_desconhecido_recusa(monkeypatch, coletor):
    resultado, chamadas = _coletar(monkeypatch, coletor, _config(**_termos("talvez")))
    assert chamadas == 0
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos


def test_fonte_desativada_nao_e_coletada(monkeypatch, coletor):
    resultado, chamadas = _coletar(
        monkeypatch, coletor, _config(ativa=False, **_termos("permite"))
    )
    assert chamadas == 0
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos


@pytest.mark.parametrize("ativa", ["false", "no", "nao", 0, None, "true"])
def test_ativa_nao_booleano_recusa(monkeypatch, coletor, ativa):
    resultado, chamadas = _coletar(
        monkeypatch, coletor, _config(ativa=ativa, **_termos("permite"))
    )
    assert chamadas == 0
    assert MotivoNoGo.TOS_PROIBE in resultado.motivos


@pytest.mark.parametrize("ativa", ["false", "no", 0, None])
def test_ativa_nao_booleano_sai_da_allowlist_de_dominios(monkeypatch, ativa):
    monkeypatch.setattr(
        conformidade, "carregar", lambda nome: _config(ativa=ativa, **_termos("permite"))
    )
    assert "fonte-ficticia.example.net" not in dominios_permitidos()


def test_fonte_fora_do_yaml_recusa(monkeypatch):
    monkeypatch.setattr(conformidade, "carregar", lambda nome: _config())
    with pytest.raises(TermosNaoPermitem):
        exigir_termos_permitidos("outra")


def test_fonte_desativada_sai_da_allowlist_de_dominios(monkeypatch):
    monkeypatch.setattr(
        conformidade, "carregar", lambda nome: _config(ativa=False, **_termos("proibe"))
    )
    assert "fonte-ficticia.example.net" not in dominios_permitidos()


def _pendente(fonte: dict) -> bool:
    return (fonte.get("termos") or {}).get("veredito") == "pendente"


def test_yaml_real_toda_fonte_tem_termos_revisados():
    fontes = carregar("fontes")["fontes"]
    for slug, fonte in fontes.items():
        termos = fonte.get("termos") or {}
        assert termos.get("link", "").startswith("https://"), slug
        if _pendente(fonte):
            assert not termos.get("revisado_em"), slug
            continue
        assert termos.get("revisado_em"), slug
        assert termos.get("veredito") in {*VEREDITOS_COLETAVEIS, "proibe"}, slug


def test_yaml_real_nenhuma_fonte_ativa_proibe():
    fontes = carregar("fontes")["fontes"]
    for slug, fonte in fontes.items():
        if fonte["termos"]["veredito"] == "proibe":
            assert fonte.get("ativa") is False, slug
        if fonte.get("ativa") is False:
            assert fonte["termos"]["veredito"] in {"proibe", "pendente"}, slug


def test_yaml_real_fonte_com_termos_pendentes_fica_desligada():
    pendentes = [s for s, f in carregar("fontes")["fontes"].items() if _pendente(f)]
    assert pendentes
    for slug in pendentes:
        assert carregar("fontes")["fontes"][slug].get("ativa") is False, slug
        with pytest.raises(TermosNaoPermitem):
            exigir_termos_permitidos(slug)
        assert not any(
            d in dominios_permitidos() for d in carregar("fontes")["fontes"][slug]["dominios"]
        ), slug


def test_yaml_real_ativa_so_booleano():
    for slug, fonte in carregar("fontes")["fontes"].items():
        assert fonte.get("ativa", True) in (True, False), slug
        assert isinstance(fonte.get("ativa", True), bool), slug


def test_yaml_real_fonte_ativa_passa_na_regra():
    fontes = carregar("fontes")["fontes"]
    for slug, fonte in fontes.items():
        if fonte.get("ativa") is not False:
            exigir_termos_permitidos(slug)


def test_doc_cobre_todas_as_fontes_e_a_gupy():
    texto = (RAIZ / "docs/fontes-termos.md").read_text(encoding="utf-8").lower()
    revisadas = [s for s, f in carregar("fontes")["fontes"].items() if not _pendente(f)]
    for slug in [*revisadas, "gupy"]:
        assert f"`{slug}`" in texto, slug
