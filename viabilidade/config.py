from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent

load_dotenv(RAIZ / ".env")


@dataclass(frozen=True, slots=True)
class Ambiente:
    user_agent: str
    timeout: float
    rate_limit_rps: float
    egress_modo: str
    egress_perfil: Path
    token_submit_real: str
    dados: Path

    @property
    def submit_real_autorizado(self) -> bool:
        return self.egress_modo == "submit_real" and len(self.token_submit_real) >= 16


@lru_cache(maxsize=1)
def ambiente() -> Ambiente:
    return Ambiente(
        user_agent=os.getenv("PLEITO_USER_AGENT", "pleito/0.1"),
        timeout=float(os.getenv("PLEITO_HTTP_TIMEOUT", "20")),
        rate_limit_rps=float(os.getenv("PLEITO_RATE_LIMIT_RPS", "0.5")),
        egress_modo=os.getenv("PLEITO_EGRESS_MODO", "dry_run"),
        egress_perfil=Path(os.getenv("PLEITO_EGRESS_PERFIL", RAIZ / "segredos/perfil_navegador")),
        token_submit_real=os.getenv("PLEITO_EGRESS_TOKEN_SUBMIT_REAL", ""),
        dados=RAIZ / "dados",
    )


@lru_cache(maxsize=8)
def carregar(nome: str) -> dict:
    caminho = RAIZ / "config" / f"{nome}.yaml"
    with caminho.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
