from __future__ import annotations

import argparse
import plistlib
from pathlib import Path

from src.agendamento.configuracao import Agendamento, agendamento_do_config
from src.config import RAIZ, carregar


def gerar_plist(cfg: Agendamento, raiz: Path, log: Path) -> bytes:
    janelas = [
        {"Hour": hora, "Minute": minuto}
        for hora, minuto in sorted(r.hora_e_minuto for r in cfg.rotinas if r.horario)
    ]
    intervalos = [r.intervalo_min for r in cfg.rotinas if r.intervalo_min]
    conteudo: dict = {
        "Label": cfg.rotulo,
        "ProgramArguments": [str(raiz / ".venv/bin/python"), "-m", "src.agendamento.executor"],
        "WorkingDirectory": str(raiz),
        "RunAtLoad": True,
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    }
    if janelas:
        conteudo["StartCalendarInterval"] = janelas
    if intervalos:
        conteudo["StartInterval"] = min(intervalos) * 60
    return plistlib.dumps(conteudo)


def main() -> None:
    bloco = carregar("limites")["agendamento"]
    argumentos = argparse.ArgumentParser(description="Gera o plist do launchd sem instalar")
    argumentos.add_argument("--saida", type=Path, default=RAIZ / bloco["saida_plist"])
    opcoes = argumentos.parse_args()
    log = RAIZ / bloco["log"]
    opcoes.saida.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    opcoes.saida.write_bytes(gerar_plist(agendamento_do_config(), RAIZ, log))
    print(opcoes.saida)


if __name__ == "__main__":
    main()
