from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from src.agendamento.configuracao import Agendamento, Rotina, agendamento_do_config
from src.config import RAIZ, carregar

Corredor = Callable[[Rotina], int]


class EstouroDeTempo(Exception):
    pass


def ler_registro(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar_registro(caminho: Path, entradas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_text(json.dumps(entradas, indent=1), encoding="utf-8")
    os.replace(temporario, caminho)


def janela_mais_recente(rotina: Rotina, agora: datetime) -> datetime:
    hora, minuto = rotina.hora_e_minuto
    hoje = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    return hoje if hoje <= agora else hoje - timedelta(days=1)


def ultima_execucao(entradas: list[dict], nome: str) -> datetime | None:
    momentos = [
        datetime.fromisoformat(e["em"])
        for e in entradas
        if e["rotina"] == nome and e["status"] in ("ok", "falha")
    ]
    return max(momentos, default=None)


def entrada(rotina: Rotina, janela: str | None, agora: datetime, status: str, recuperada: bool):
    return {
        "rotina": rotina.nome,
        "janela": janela,
        "em": agora.isoformat(),
        "status": status,
        "recuperada": recuperada,
    }


def executar(cfg: Agendamento, registro: Path, agora: datetime, corredor: Corredor) -> None:
    entradas = ler_registro(registro)
    tolerancia = timedelta(minutes=cfg.tolerancia_min)
    for rotina in cfg.rotinas:
        if rotina.horario:
            janela = janela_mais_recente(rotina, agora)
            identificador = janela.isoformat()
            if any(e["rotina"] == rotina.nome and e["janela"] == identificador for e in entradas):
                continue
            recuperada = agora - janela > tolerancia
            if recuperada and not cfg.retry_ao_acordar:
                entradas.append(entrada(rotina, identificador, agora, "perdida", False))
                gravar_registro(registro, entradas)
                continue
        else:
            ultima = ultima_execucao(entradas, rotina.nome)
            if ultima and agora - ultima < timedelta(minutes=rotina.intervalo_min) - tolerancia:
                continue
            identificador = None
            recuperada = False
        try:
            status = "ok" if corredor(rotina) == 0 else "falha"
        except EstouroDeTempo:
            status = "timeout"
        entradas.append(entrada(rotina, identificador, agora, status, recuperada))
        gravar_registro(registro, entradas)


def correr_comando(rotina: Rotina, timeout_min: int) -> int:
    try:
        return subprocess.run(
            rotina.comando, cwd=RAIZ, check=False, timeout=timeout_min * 60
        ).returncode
    except subprocess.TimeoutExpired as erro:
        raise EstouroDeTempo from erro


def main() -> None:
    bloco = carregar("limites")["agendamento"]
    cfg = agendamento_do_config()
    executar(
        cfg,
        RAIZ / bloco["registro"],
        datetime.now(),
        lambda rotina: correr_comando(rotina, cfg.timeout_min),
    )


if __name__ == "__main__":
    main()
