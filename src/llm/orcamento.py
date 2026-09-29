from __future__ import annotations

from decimal import Decimal


class OrcamentoEsgotado(RuntimeError):
    pass


def calcular_limite_diario(
    orcamento_mensal: Decimal,
    limite_diario: Decimal,
    gasto_mensal: Decimal,
    dias_restantes: int,
) -> Decimal:
    if dias_restantes < 1:
        raise ValueError("dias restantes precisa ser positivo")
    saldo = max(orcamento_mensal - gasto_mensal, Decimal("0"))
    return min(limite_diario, saldo / dias_restantes)


def exigir_saldo_tier(tier: str, saldo: Decimal, saldo_minimo_forte: Decimal) -> None:
    if tier == "forte" and saldo < saldo_minimo_forte:
        raise OrcamentoEsgotado("saldo mensal insuficiente para o tier forte")
