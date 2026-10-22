from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from src.email.configuracao import configuracao_gmail
from src.email.keychain import Keychain
from src.email.oauth import autorizar


def main() -> None:
    cfg = configuracao_gmail()
    chave = Keychain(cfg.keychain_binario, cfg.keychain_servico, cfg.keychain_conta)
    print("Abrindo o navegador para autorizar o Gmail com os escopos:")
    for escopo in cfg.escopos:
        print(f"  {escopo}")
    with httpx.Client() as http:
        autorizar(cfg, chave, http)
    print(f"Token guardado no Keychain (servico {cfg.keychain_servico}).")


if __name__ == "__main__":
    main()
