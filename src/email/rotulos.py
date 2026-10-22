from __future__ import annotations

from src.config import carregar
from src.email.modelo import Etapa


def rotulo_da_etapa(etapa: Etapa) -> str:
    return carregar("rotulos")["etapas"][etapa.value]
