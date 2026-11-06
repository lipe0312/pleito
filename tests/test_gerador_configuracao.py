from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from src.config import carregar
from src.gerador.compilar import ambiente_do_motor
from src.gerador.configuracao import configuracao_gerador


def _dados(**compilacao) -> dict:
    dados = carregar("gerador")
    return dados | {"compilacao": dados["compilacao"] | compilacao}


def _sem(chave: str) -> dict:
    ambiente = dict(carregar("gerador")["compilacao"]["ambiente"])
    del ambiente[chave]
    return ambiente


@pytest.mark.parametrize("chave", ["openin_any", "openout_any", "shell_escape"])
def test_config_sem_trava_de_arquivo_ou_shell_e_recusada(chave):
    with pytest.raises(ValidationError):
        configuracao_gerador(_dados(ambiente=_sem(chave)))


@pytest.mark.parametrize(
    "ambiente",
    [
        {"openin_any": "a", "openout_any": "p", "shell_escape": "f"},
        {"openin_any": "p", "openout_any": "a", "shell_escape": "f"},
        {"openin_any": "p", "openout_any": "p", "shell_escape": "t"},
        {"openin_any": "p", "openout_any": "p", "shell_escape": "p"},
    ],
)
def test_config_com_trava_afrouxada_e_recusada(ambiente):
    with pytest.raises(ValidationError):
        configuracao_gerador(_dados(ambiente=ambiente))


def test_config_sem_no_shell_escape_e_recusada():
    with pytest.raises(ValidationError):
        configuracao_gerador(_dados(argumentos=["-interaction=nonstopmode"]))


def test_config_do_repositorio_e_aceita_e_traz_o_limite_de_linhas_do_erro():
    assert configuracao_gerador().compilacao.linhas_do_erro > 0


def test_ambiente_do_motor_nao_herda_variaveis_de_tex_nem_segredos(monkeypatch):
    for nome in ("TEXINPUTS", "TEXMFHOME", "TEXMFCNF", "TEXFORMATS", "OPENAI_API_KEY", "TOKEN_X"):
        monkeypatch.setenv(nome, "/hostil/tex")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/casa/fake")
    config = configuracao_gerador()

    ambiente = ambiente_do_motor(config.compilacao)

    assert ambiente == {"PATH": "/usr/bin", "HOME": "/casa/fake"} | config.compilacao.ambiente
    assert not {"TEXINPUTS", "TEXMFHOME", "TEXMFCNF", "OPENAI_API_KEY", "TOKEN_X"} & set(ambiente)


def test_ambiente_do_motor_ignora_herdada_ausente(monkeypatch):
    monkeypatch.delenv("HOME", raising=False)
    config = configuracao_gerador()

    ambiente = ambiente_do_motor(config.compilacao)

    assert "HOME" not in ambiente
    assert ambiente["PATH"] == os.environ["PATH"]


def test_config_nao_deixa_o_ambiente_fixo_sobrescrever_nome_herdado():
    ambiente = {"openin_any": "p", "openout_any": "p", "shell_escape": "f", "PATH": "/hostil"}
    with pytest.raises(ValidationError):
        configuracao_gerador(_dados(ambiente=ambiente))
