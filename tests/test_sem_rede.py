from __future__ import annotations

import socket

import httpx
import pytest


def test_teste_padrao_nao_alcanca_host_externo():
    with socket.socket() as soquete, pytest.raises(AssertionError, match="rede externa"):
        soquete.connect(("93.184.216.34", 80))


def test_coletor_real_nao_sai_do_teste_padrao():
    with pytest.raises(AssertionError, match="rede externa"):
        httpx.get("https://boards-api.greenhouse.io/v1/boards/x/jobs", timeout=1)
