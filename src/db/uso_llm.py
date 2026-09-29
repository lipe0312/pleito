from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from src.db.conexao import conectar
from src.llm.orcamento import OrcamentoEsgotado, calcular_limite_diario, exigir_saldo_tier
from viabilidade.config import carregar


def _limites() -> tuple[Decimal, Decimal]:
    llm = carregar("limites")["llm"]
    return Decimal(str(llm["orcamento_mensal_usd"])), Decimal(
        str(llm["orcamento_usd_dia_max"])
    )


def _inicio_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.min, tzinfo=UTC)


def reservar_uso_llm(
    etapa: str,
    provedor: str,
    modelo: str,
    tier: str,
    prompt_versao: str,
    custo_maximo_usd: Decimal,
    agora: datetime | None = None,
) -> int:
    if custo_maximo_usd <= 0:
        raise ValueError("custo maximo precisa ser positivo")
    if agora is not None and agora.utcoffset() is None:
        raise ValueError("data da reserva precisa ter fuso horario")
    instante = agora.astimezone(UTC) if agora is not None else None
    mensal, diario_maximo = _limites()
    saldo_minimo_forte = Decimal(str(carregar("limites")["llm"]["saldo_minimo_forte_usd"]))
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (930172,))
        if instante is None:
            cursor.execute("SELECT now()")
            instante = cursor.fetchone()[0].astimezone(UTC)
        inicio_mes = instante.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        inicio_dia = _inicio_dia(instante.date())
        proximo_dia = inicio_dia + timedelta(days=1)
        inicio_proximo_mes = (inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1)
        dias_restantes = (inicio_proximo_mes.date() - instante.date()).days
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(custo_usd + custo_reservado_usd)
                    FILTER (WHERE ocorrido_em >= %s), 0),
                COALESCE(SUM(custo_usd + custo_reservado_usd)
                    FILTER (WHERE ocorrido_em >= %s AND ocorrido_em < %s), 0)
            FROM uso_llm
            WHERE estado IN ('reservado', 'concluido')
              AND ocorrido_em >= %s
            """,
            (inicio_mes, inicio_dia, proximo_dia, inicio_mes),
        )
        gasto_mes, gasto_dia = (Decimal(str(v)) for v in cursor.fetchone())
        saldo_mes = max(mensal - gasto_mes, Decimal("0"))
        exigir_saldo_tier(tier, saldo_mes, saldo_minimo_forte)
        limite_dia = calcular_limite_diario(mensal, diario_maximo, gasto_mes, dias_restantes)
        if custo_maximo_usd > saldo_mes or gasto_dia + custo_maximo_usd > limite_dia:
            raise OrcamentoEsgotado("orcamento LLM insuficiente para reservar a chamada")
        cursor.execute(
            """
            INSERT INTO uso_llm (
                etapa, provedor, modelo, tier, prompt_versao, custo_reservado_usd
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                etapa,
                provedor,
                modelo,
                tier,
                prompt_versao,
                custo_maximo_usd,
            ),
        )
        return cursor.fetchone()[0]


def finalizar_uso_llm(
    uso_id: int,
    tokens_entrada: int,
    tokens_saida: int,
    custo_usd: Decimal,
    resultado_validacao: str,
) -> None:
    if min(tokens_entrada, tokens_saida) < 0 or custo_usd < 0:
        raise ValueError("uso LLM nao pode registrar valores negativos")
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute(
            """
            UPDATE uso_llm
            SET tokens_entrada = %s,
                tokens_saida = %s,
                custo_usd = %s,
                custo_reservado_usd = 0,
                resultado_validacao = %s,
                estado = 'concluido',
                concluido_em = now()
            WHERE id = %s AND estado = 'reservado'
            """,
            (tokens_entrada, tokens_saida, custo_usd, resultado_validacao, uso_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("reserva LLM ausente ou ja finalizada")


def falhar_uso_llm(uso_id: int, erro_tipo: str) -> None:
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute(
            """
            UPDATE uso_llm
            SET custo_reservado_usd = 0,
                resultado_validacao = 'falha',
                estado = 'falhou',
                erro_tipo = %s,
                concluido_em = now()
            WHERE id = %s AND estado = 'reservado'
            """,
            (erro_tipo, uso_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("reserva LLM ausente ou ja finalizada")
