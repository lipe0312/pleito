from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

MARCADOR = re.compile(r"^backlog:\s*(\S+)\s*$", re.MULTILINE)


def rodar(*comando: str) -> str:
    resultado = subprocess.run(comando, capture_output=True, text=True)
    return resultado.stdout.strip() if resultado.returncode == 0 else ""


def ler_json(*comando: str) -> list:
    saida = rodar(*comando)
    if not saida:
        return []
    try:
        return json.loads(saida)
    except json.JSONDecodeError:
        return [json.loads(linha) for linha in saida.splitlines() if linha.strip()]


def raiz() -> Path:
    for linha in rodar("git", "worktree", "list", "--porcelain").splitlines():
        if linha.startswith("worktree "):
            return Path(linha.split(" ", 1)[1])
    return Path.cwd()


def carregar_backlog(base: Path | None = None) -> dict:
    caminho = (base or raiz()) / "config" / "backlog.yaml"
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def ordem(item_id: str) -> tuple:
    return tuple(int(n) if n.isdigit() else n for n in re.findall(r"\d+|[A-Z]+", item_id))


def marcador(corpo: str | None) -> str | None:
    achado = MARCADOR.search(corpo or "")
    return achado.group(1) if achado else None


def concluida(issue: dict) -> bool:
    return issue["state"] == "closed" and issue.get("state_reason") != "not_planned"


def preferida(atual: dict | None, nova: dict) -> dict:
    if atual is None:
        return nova
    if (atual["state"] == "open") != (nova["state"] == "open"):
        return atual if atual["state"] == "open" else nova
    if concluida(atual) != concluida(nova):
        return atual if concluida(atual) else nova
    return atual if atual["number"] > nova["number"] else nova


def mapear_issues(issues: list[dict], conhecidos: set[str]) -> tuple[dict[str, dict], list[dict]]:
    por_id: dict[str, dict] = {}
    avulsas = []
    for issue in issues:
        chave = marcador(issue.get("body"))
        if chave in conhecidos:
            por_id[chave] = preferida(por_id.get(chave), issue)
        elif issue["state"] == "open":
            avulsas.append(issue)
    return por_id, avulsas


@dataclass
class Frente:
    chave: str
    zona: str
    schema: bool


@dataclass
class Plano:
    ondas: list[list[str]] = field(default_factory=list)
    sem_onda: dict[str, list[str]] = field(default_factory=dict)


def calcular_ondas(
    itens: dict[str, dict],
    concluidos: set[str],
    ocupadas: list[Frente],
    frentes: int,
) -> Plano:
    plano = Plano()
    em_andamento = {f.chave for f in ocupadas}
    pendentes = [i for i in sorted(itens, key=ordem) if i not in concluidos | em_andamento]
    antes = set(concluidos)
    primeira = True
    while pendentes:
        zonas = {f.zona for f in ocupadas} if primeira else set()
        schema_usado = any(f.schema for f in ocupadas) if primeira else False
        vagas = frentes - (len(ocupadas) if primeira else 0)
        onda: list[str] = []
        prontos = sorted(
            (i for i in pendentes if all(d in antes for d in itens[i]["depende"])),
            key=lambda i: (itens[i]["fase"], ordem(i)),
        )
        for item_id in prontos:
            if len(onda) >= max(vagas, 0):
                break
            item = itens[item_id]
            if item["zona"] in zonas or (item["schema"] and schema_usado):
                continue
            onda.append(item_id)
            zonas.add(item["zona"])
            schema_usado = schema_usado or item["schema"]
        if not onda and not (primeira and ocupadas):
            for item_id in pendentes:
                plano.sem_onda[item_id] = [d for d in itens[item_id]["depende"] if d not in antes]
            break
        plano.ondas.append(onda)
        antes |= set(onda) | (em_andamento if primeira else set())
        pendentes = [i for i in pendentes if i not in onda]
        primeira = False
    return plano
