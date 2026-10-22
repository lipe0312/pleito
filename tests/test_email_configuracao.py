from __future__ import annotations

import copy
import ipaddress

import pytest

from src.config import RAIZ, carregar
from src.email.configuracao import (
    ESCOPOS_PERMITIDOS,
    EscopoProibido,
    LoopbackInvalido,
    RotuloRecusado,
    configuracao_gmail,
)


def _dados() -> dict:
    return copy.deepcopy(carregar("emails"))


def test_config_versionado_carrega_so_escopos_permitidos():
    cfg = configuracao_gmail(_dados())
    assert cfg.escopos
    assert set(cfg.escopos) <= ESCOPOS_PERMITIDOS
    assert cfg.caminho_cliente == RAIZ / "segredos" / "gmail_cliente.json"


@pytest.mark.parametrize(
    "escopo",
    [
        "https://www.googleapis.com/auth/gmail.send",
        "https://mail.google.com/",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.insert",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/gmail.modify https://mail.google.com/",
    ],
)
def test_escopo_extra_injetado_no_config_e_recusado(escopo):
    dados = _dados()
    dados["gmail"]["escopos"].append(escopo)
    with pytest.raises(EscopoProibido):
        configuracao_gmail(dados)


def test_lista_de_escopos_vazia_e_recusada():
    dados = _dados()
    dados["gmail"]["escopos"] = []
    with pytest.raises(EscopoProibido):
        configuracao_gmail(dados)


TODAS_AS_INTERFACES = str(ipaddress.IPv4Address(0))


@pytest.mark.parametrize(
    "host", [TODAS_AS_INTERFACES, "192.168.0.10", "::1", "exemplo.invalido"]
)
def test_loopback_fora_do_localhost_e_recusado(host):
    dados = _dados()
    dados["gmail"]["loopback"]["host"] = host
    with pytest.raises(LoopbackInvalido):
        configuracao_gmail(dados)


@pytest.mark.parametrize("rotulo", ["TRASH", "SPAM", "SENT", "DRAFT", "INBOX"])
def test_rotulo_de_sistema_destrutivo_na_allowlist_do_config_e_recusado(rotulo):
    dados = _dados()
    dados["gmail"]["rotulos_sistema_permitidos"].append(rotulo)
    with pytest.raises(RotuloRecusado):
        configuracao_gmail(dados)


def test_teto_de_listagem_precisa_ser_positivo():
    dados = _dados()
    dados["gmail"]["listar_maximo"] = 0
    with pytest.raises(ValueError):
        configuracao_gmail(dados)
