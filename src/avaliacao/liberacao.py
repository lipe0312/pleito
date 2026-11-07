from __future__ import annotations

from copy import deepcopy
from datetime import date


def tiers_habilitados_sem_aprovacao(modelos: dict) -> list[str]:
    pendentes = []
    for nome, tier in (modelos.get("tiers") or {}).items():
        avaliacao = tier.get("avaliacao") or {}
        aprovado = (
            avaliacao.get("status") == "aprovado"
            and bool(avaliacao.get("conjunto"))
            and bool(avaliacao.get("data"))
        )
        if tier.get("habilitado") and not aprovado:
            pendentes.append(nome)
    return pendentes


def configuracao_em_avaliacao(modelos: dict, tier: str, versao_conjunto: str, hoje: date) -> dict:
    copia = deepcopy(modelos)
    for nome, dados in copia["tiers"].items():
        dados["habilitado"] = False
        if nome == tier:
            dados["habilitado"] = True
            dados["avaliacao"] = {
                "status": "aprovado",
                "conjunto": f"em_avaliacao:{versao_conjunto}",
                "data": hoje.isoformat(),
            }
    return copia
