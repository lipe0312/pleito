from __future__ import annotations

import posixpath
import re
import subprocess
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatchcase

MODO_SYMLINK = "120000"
MODO_SUBMODULO = "160000"
PREFIXO_COMENTARIO = "#"


@dataclass(frozen=True, slots=True)
class Achado:
    onde: str
    regra: str


def normalizar(caminho: str) -> str:
    unificado = unicodedata.normalize("NFC", caminho).replace("\\", "/").casefold()
    return posixpath.normpath(unificado)


def fora_da_raiz(normalizado: str) -> bool:
    return normalizado.startswith("/") or normalizado == ".." or normalizado.startswith("../")


def caminho_proibido(caminho: str, regras: dict) -> bool:
    normalizado = normalizar(caminho)
    if fora_da_raiz(normalizado):
        return True
    if normalizado in {normalizar(excecao) for excecao in regras.get("excecoes", [])}:
        return False
    segmentos = set(normalizado.split("/"))
    if segmentos & {normalizar(nome) for nome in regras.get("segmentos_proibidos", [])}:
        return True
    return any(fnmatchcase(normalizado, normalizar(padrao)) for padrao in regras["proibidos"])


def compilar(regras: Iterable[dict]) -> list[tuple[str, re.Pattern[str]]]:
    return [(regra["nome"], re.compile(regra["expressao"])) for regra in regras]


def procurar_segredos(linhas: Iterable[str], regras: Iterable[dict]) -> list[Achado]:
    compiladas = compilar(regras)
    achados = []
    for numero, linha in enumerate(linhas, start=1):
        for nome, expressao in compiladas:
            if expressao.search(linha):
                achados.append(Achado(onde=str(numero), regra=nome))
    return achados


def procurar_atribuicao(linhas: Iterable[str], regras: Iterable[dict]) -> list[Achado]:
    uteis = [
        (numero, linha)
        for numero, linha in enumerate(linhas, start=1)
        if not linha.lstrip().startswith(PREFIXO_COMENTARIO)
    ]
    compiladas = compilar(regras)
    return [
        Achado(onde=str(numero), regra=nome)
        for numero, linha in uteis
        for nome, expressao in compiladas
        if expressao.search(linha)
    ]


def executar_git(argumentos: list[str]) -> bytes:
    return subprocess.run(
        ["git", *argumentos],
        check=True,
        capture_output=True,
    ).stdout


def arquivos_staged() -> list[tuple[str, str]]:
    saida = executar_git(
        ["diff", "--cached", "--raw", "-z", "--no-renames", "--no-ext-diff", "--diff-filter=ACMRT"]
    ).decode("utf-8", errors="replace")
    campos = saida.split("\0")
    pares = []
    for indice in range(0, len(campos) - 1, 2):
        modo_novo = campos[indice].split()[1] if campos[indice] else ""
        pares.append((campos[indice + 1], modo_novo))
    return pares


def verificar_arquivos(regras: dict) -> list[Achado]:
    achados = []
    for caminho, modo in arquivos_staged():
        if regras.get("recusar_symlink") and modo == MODO_SYMLINK:
            achados.append(Achado(onde=caminho, regra="symlink"))
        elif regras.get("recusar_submodulo") and modo == MODO_SUBMODULO:
            achados.append(Achado(onde=caminho, regra="submodulo"))
        elif caminho_proibido(caminho, regras):
            achados.append(Achado(onde=caminho, regra="caminho_proibido"))
    return achados


def linhas_adicionadas() -> Iterable[tuple[str, int, str]]:
    saida = executar_git(
        [
            "-c",
            "core.quotepath=false",
            "diff",
            "--cached",
            "-U0",
            "--no-color",
            "--text",
            "--no-textconv",
            "--no-ext-diff",
            "--no-renames",
            "--diff-filter=ACMRT",
        ]
    ).decode("utf-8", errors="replace")
    arquivo = ""
    numero = 0
    em_trecho = False
    for linha in saida.split("\n"):
        if linha.startswith("diff --git "):
            em_trecho = False
            arquivo = ""
        elif em_trecho:
            if linha.startswith("+"):
                yield arquivo, numero, linha[1:].removesuffix("\r")
                numero += 1
        elif linha.startswith("+++ "):
            arquivo = linha[4:].removeprefix("b/")
        elif linha.startswith("@@"):
            correspondencia = re.search(r"\+(\d+)", linha)
            numero = int(correspondencia.group(1)) if correspondencia else 0
            em_trecho = True


def verificar_diff(regras: Iterable[dict]) -> list[Achado]:
    compiladas = compilar(regras)
    achados = []
    for arquivo, numero, texto in linhas_adicionadas():
        for nome, expressao in compiladas:
            if expressao.search(texto):
                achados.append(Achado(onde=f"{arquivo}:{numero}", regra=nome))
    return achados


def verificar_mensagem(caminho: str, regras: Iterable[dict]) -> list[Achado]:
    with open(caminho, encoding="utf-8", errors="replace") as arquivo:
        linhas = arquivo.read().splitlines()
    return procurar_atribuicao(linhas, regras)
