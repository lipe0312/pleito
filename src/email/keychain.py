from __future__ import annotations

import subprocess
from collections.abc import Callable

CODIGO_ITEM_AUSENTE = 44
CARACTERES_PROIBIDOS = frozenset("\"'\\")

Executor = Callable[[list[str], str | None], subprocess.CompletedProcess]


class TokenAusente(LookupError):
    pass


class ValorRecusado(ValueError):
    pass


class ErroKeychain(RuntimeError):
    pass


def executar_security(argumentos: list[str], entrada: str | None) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        argumentos,
        input=entrada,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )


def citar(valor: str) -> str:
    if not valor:
        raise ValorRecusado("valor vazio")
    for caractere in valor:
        if caractere in CARACTERES_PROIBIDOS or caractere.isspace() or not caractere.isprintable():
            raise ValorRecusado("valor com aspas, barra invertida, espaco ou caractere de controle")
    return f'"{valor}"'


class Keychain:
    def __init__(
        self,
        binario: str,
        servico: str,
        conta: str,
        executor: Executor = executar_security,
    ) -> None:
        self.binario = binario
        self.servico = servico
        self.conta = conta
        self.executor = executor

    def ler(self) -> str:
        resultado = self.executor(
            [self.binario, "find-generic-password", "-s", self.servico, "-a", self.conta, "-w"],
            None,
        )
        if resultado.returncode == CODIGO_ITEM_AUSENTE:
            raise TokenAusente(self.servico)
        if resultado.returncode != 0:
            raise ErroKeychain(f"leitura falhou com codigo {resultado.returncode}")
        return resultado.stdout.rstrip("\n")

    def gravar(self, valor: str) -> None:
        comando = (
            f"add-generic-password -U -s {citar(self.servico)} -a {citar(self.conta)} "
            f"-w {citar(valor)}\n"
        )
        resultado = self.executor([self.binario, "-i"], comando)
        if resultado.returncode != 0:
            raise ErroKeychain(f"gravacao falhou com codigo {resultado.returncode}")
        try:
            confirmado = self.ler()
        except TokenAusente as erro:
            raise ErroKeychain("gravacao nao confirmada") from erro
        if confirmado != valor:
            raise ErroKeychain("gravacao nao confirmada")
