from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from src.gerador.configuracao import ConfiguracaoGerador
from src.validador.resultado import Resultado


def agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def gravar_json(caminho: Path, dados: object) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def ler_json(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def pasta_das_tentativas(pasta: Path, config: ConfiguracaoGerador) -> Path:
    return pasta / config.laco.pasta_tentativas


def proxima_tentativa(pasta: Path, config: ConfiguracaoGerador) -> int:
    raiz = pasta_das_tentativas(pasta, config)
    numeros = [
        int(item.name)
        for item in raiz.glob("*")
        if item.is_dir() and re.fullmatch("[0-9]+", item.name)
    ]
    return max(numeros, default=0) + 1


def nova_pasta_de_tentativa(pasta: Path, numero: int, config: ConfiguracaoGerador) -> Path:
    destino = pasta_das_tentativas(pasta, config) / str(numero)
    destino.mkdir(parents=True, exist_ok=False)
    return destino


def violacoes_em_json(resultado: Resultado | None) -> list[dict]:
    if resultado is None:
        return []
    return [
        {
            "codigo": violacao.codigo,
            "regra": str(violacao.regra),
            "nivel": str(violacao.nivel),
            "detalhe": violacao.detalhe,
            "trecho": violacao.trecho,
            "sugestao": violacao.sugestao,
        }
        for violacao in resultado.violacoes
    ]


def resumo_das_regras(resultado: Resultado | None) -> dict:
    if resultado is None:
        return {"aprovado": False, "bloqueios": [], "indicios": []}
    return {
        "aprovado": resultado.aprovado,
        "bloqueios": list(dict.fromkeys(v.codigo or str(v.regra) for v in resultado.bloqueios)),
        "indicios": list(dict.fromkeys(v.codigo or str(v.regra) for v in resultado.indicios)),
    }


def ler_historico(pasta: Path, config: ConfiguracaoGerador) -> dict:
    caminho = pasta / config.laco.arquivos.historico
    if not caminho.is_file():
        return {"versoes": [], "refacoes": []}
    return ler_json(caminho)


def gravar_historico(pasta: Path, historico: dict, config: ConfiguracaoGerador) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    gravar_json(pasta / config.laco.arquivos.historico, historico)


def _diferenca(antes: dict | None, depois: dict) -> dict:
    nomes = list(dict.fromkeys([*(antes or {}), *depois]))
    return {
        nome: {"antes": (antes or {}).get(nome), "depois": depois.get(nome)}
        for nome in nomes
        if antes is None or antes.get(nome) != depois.get(nome)
    }


def publicar(
    pasta: Path,
    tentativa: Path,
    numero: int,
    extras: dict,
    config: ConfiguracaoGerador,
) -> dict:
    arquivos = config.laco.arquivos
    nome = config.compilacao.nome_arquivo
    historico = ler_historico(pasta, config)
    anterior = historico["versoes"][-1]["tentativa"] if historico["versoes"] else None
    slots_anteriores = (
        ler_json(pasta_das_tentativas(pasta, config) / str(anterior) / arquivos.slots)
        if anterior is not None
        else None
    )
    for arquivo in (f"{nome}.tex", f"{nome}.pdf", arquivos.validacao):
        shutil.copyfile(tentativa / arquivo, pasta / arquivo)
    versao = len(historico["versoes"]) + 1
    gravar_json(
        pasta / arquivos.diff,
        {
            "versao": versao,
            "tentativa": numero,
            "tentativa_anterior": anterior,
            "slots": _diferenca(slots_anteriores, ler_json(tentativa / arquivos.slots)),
            "corte": ler_json(tentativa / arquivos.meta).get("corte", []),
        },
    )
    pdf = (pasta / f"{nome}.pdf").read_bytes()
    registro = {
        "versao": versao,
        "tentativa": numero,
        "criada_em": agora(),
        "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
    } | extras
    historico["versoes"].append(registro)
    gravar_historico(pasta, historico, config)
    return registro
