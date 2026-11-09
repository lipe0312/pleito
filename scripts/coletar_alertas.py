from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from src.coletor.alertas_coleta import DestinoNoBanco, configuracao_coleta, rodada_alertas
from src.db.conexao import conectar
from src.email.configuracao import configuracao_gmail
from src.email.gmail import ClienteGmail
from src.email.keychain import Keychain


def main() -> None:
    argumentos = argparse.ArgumentParser(description="Le os alertas de vaga do Gmail")
    argumentos.add_argument("--forcar", action="store_true", help="ignora o intervalo minimo")
    opcoes = argumentos.parse_args()
    cfg = configuracao_gmail()
    chave = Keychain(cfg.keychain_binario, cfg.keychain_servico, cfg.keychain_conta)
    with httpx.Client() as http, conectar("app") as conexao:
        resumo = rodada_alertas(
            ClienteGmail(cfg, chave, http),
            configuracao_coleta(),
            datetime.now(UTC),
            DestinoNoBanco(conexao),
            forcar=opcoes.forcar,
        )
    if resumo.adiada:
        print("intervalo minimo ainda nao passou; use --forcar para rodar agora")
        return
    for tipo, total in sorted(resumo.por_tipo.items()):
        print(f"{tipo.value}: {total}")
    print(f"vagas enviadas ao funil: {resumo.vagas_enviadas}")
    print(
        f"emails lidos: {resumo.lidos} · ja lidos antes: {resumo.repetidos}"
        f" · de outras origens: {resumo.ignorados} · sumidos antes da leitura: {resumo.sumidas}"
    )


if __name__ == "__main__":
    main()
