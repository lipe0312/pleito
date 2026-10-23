from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from src.email.configuracao import configuracao_gmail
from src.email.gmail import ClienteGmail
from src.email.keychain import Keychain
from src.email.organizador import configuracao_organizacao, rodada


def main() -> None:
    argumentos = argparse.ArgumentParser(description="Rotula e arquiva os emails novos")
    argumentos.add_argument("--forcar", action="store_true", help="ignora o intervalo minimo")
    opcoes = argumentos.parse_args()
    cfg = configuracao_gmail()
    chave = Keychain(cfg.keychain_binario, cfg.keychain_servico, cfg.keychain_conta)
    with httpx.Client() as http:
        resumo = rodada(
            ClienteGmail(cfg, chave, http),
            configuracao_organizacao(),
            datetime.now(UTC),
            forcar=opcoes.forcar,
        )
    if resumo.adiada:
        print("intervalo minimo ainda nao passou; use --forcar para rodar agora")
        return
    for etapa, total in sorted(resumo.por_etapa.items()):
        print(f"{etapa.value}: {total}")
    print(f"ignoradas: {resumo.ignoradas} · ja fora da caixa: {resumo.fora_da_caixa}")


if __name__ == "__main__":
    main()
