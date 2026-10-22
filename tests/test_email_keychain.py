from __future__ import annotations

import subprocess

import pytest

from src.email import keychain as modulo
from src.email.keychain import (
    ErroKeychain,
    Keychain,
    TokenAusente,
    ValorRecusado,
    executar_security,
)

BINARIO = "/caminho/ficticio/security"


@pytest.fixture(autouse=True)
def proibir_security_real(monkeypatch):
    def explodir(*_args, **_kwargs):
        raise AssertionError("teste chamou subprocess real")

    monkeypatch.setattr(modulo.subprocess, "run", explodir)


class KeychainFalso:
    def __init__(self, codigo_gravar: int = 0, persistir: bool = True) -> None:
        self.chamadas: list[tuple[list[str], str | None]] = []
        self.guardado: str | None = None
        self.codigo_gravar = codigo_gravar
        self.persistir = persistir

    def __call__(self, argumentos, entrada):
        self.chamadas.append((list(argumentos), entrada))
        if argumentos[1:] == ["-i"]:
            if self.persistir and self.codigo_gravar == 0:
                self.guardado = entrada.split(" -w ", 1)[1].strip().strip('"')
            return subprocess.CompletedProcess(argumentos, self.codigo_gravar, "", "")
        if self.guardado is None:
            return subprocess.CompletedProcess(argumentos, 44, "", "")
        return subprocess.CompletedProcess(argumentos, 0, self.guardado + "\n", "")


def _keychain(executor) -> Keychain:
    return Keychain(BINARIO, "servico-ficticio", "conta-ficticia", executor)


def test_gravar_manda_comando_pelo_stdin_e_nunca_pelo_argv():
    falso = KeychainFalso()
    ficticio = "1//0token-ficticio_ABC.def~ghi"
    _keychain(falso).gravar(ficticio)
    argumentos, entrada = falso.chamadas[0]
    assert argumentos == [BINARIO, "-i"]
    assert not any(ficticio in argumento for argumento in argumentos)
    assert entrada == (
        'add-generic-password -U -s "servico-ficticio" -a "conta-ficticia" '
        f'-w "{ficticio}"\n'
    )


def test_gravar_confirma_lendo_de_volta():
    falso = KeychainFalso()
    _keychain(falso).gravar("token-ficticio")
    assert falso.chamadas[1][0] == [
        BINARIO, "find-generic-password", "-s", "servico-ficticio", "-a", "conta-ficticia", "-w",
    ]


def test_gravacao_nao_confirmada_e_erro():
    with pytest.raises(ErroKeychain):
        _keychain(KeychainFalso(persistir=False)).gravar("token-ficticio")


def test_codigo_de_erro_do_security_na_gravacao_e_erro():
    with pytest.raises(ErroKeychain):
        _keychain(KeychainFalso(codigo_gravar=1)).gravar("token-ficticio")


@pytest.mark.parametrize(
    "valor",
    [
        'abc" ; delete-generic-password -s "servico-ficticio',
        "abc\ndelete-generic-password -s servico-ficticio",
        "abc\rdelete",
        "abc'def",
        "abc\\\"def",
        "abc def",
        "abc\tdef",
        "abc\x00def",
        "",
    ],
)
def test_valor_com_aspas_quebra_de_linha_ou_escape_e_recusado_antes_do_security(valor):
    falso = KeychainFalso()
    with pytest.raises(ValorRecusado):
        _keychain(falso).gravar(valor)
    assert falso.chamadas == []


def test_erro_de_valor_recusado_nao_vaza_o_valor():
    with pytest.raises(ValorRecusado) as erro:
        _keychain(KeychainFalso()).gravar('segredo"ficticio')
    assert "segredo" not in str(erro.value)


def test_caracteres_de_shell_viram_um_unico_valor_literal():
    falso = KeychainFalso()
    hostil = "$(rm${IFS}-rf${IFS}~);|&`id`>x<y*"
    chave = _keychain(falso)
    chave.gravar(hostil)
    assert falso.chamadas[0][1].count("\n") == 1
    assert chave.ler() == hostil


def test_servico_ou_conta_com_aspas_tambem_e_recusado():
    falso = KeychainFalso()
    with pytest.raises(ValorRecusado):
        Keychain(BINARIO, 'servico" -a "outra', "conta-ficticia", falso).gravar("token")
    assert falso.chamadas == []


def test_ler_item_ausente_vira_token_ausente():
    with pytest.raises(TokenAusente):
        _keychain(KeychainFalso()).ler()


def test_ler_devolve_o_valor_sem_quebra_de_linha():
    falso = KeychainFalso()
    falso.guardado = "token-ficticio"
    assert _keychain(falso).ler() == "token-ficticio"


def test_executor_padrao_usa_lista_sem_shell(monkeypatch):
    recebido = {}

    def registrar(argumentos, **opcoes):
        recebido["argumentos"] = argumentos
        recebido.update(opcoes)
        return subprocess.CompletedProcess(argumentos, 0, "", "")

    monkeypatch.setattr(modulo.subprocess, "run", registrar)
    executar_security([BINARIO, "-i"], "comando\n")
    assert recebido["argumentos"] == [BINARIO, "-i"]
    assert recebido["shell"] is False
    assert recebido["input"] == "comando\n"
