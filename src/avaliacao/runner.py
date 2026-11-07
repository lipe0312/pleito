from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from src.avaliacao.configuracao import ConfiguracaoAvaliacao
from src.avaliacao.conjunto import Conteudo, Entrada, Lote, versao_do_conjunto
from src.avaliacao.execucao import EXECUTORES, FALHA_ESQUEMA, FALHA_PROIBIDO, Execucao
from src.avaliacao.liberacao import configuracao_em_avaliacao
from src.avaliacao.referencia import Transporte
from src.db import uso_llm
from src.llm.roteador import Roteador
from src.validador.resultado import Regra

FabricaTransporte = Callable[[Entrada, Conteudo], Transporte]
APROVADO = "aprovado"
REPROVADO = "reprovado"


@dataclass
class Medidor:
    custo: Decimal = Decimal("0")
    chamadas: int = 0
    reservas: list[int] = field(default_factory=list)

    def reservar_offline(self, **dados: object) -> int:
        self.reservas.append(len(self.reservas) + 1)
        return self.reservas[-1]

    def finalizar_com(self, real: bool) -> Callable[..., None]:
        def finalizar(uso_id, tokens_entrada, tokens_saida, custo, resultado) -> None:
            self.custo += Decimal(custo)
            self.chamadas += 1
            if real:
                uso_llm.finalizar_uso_llm(uso_id, tokens_entrada, tokens_saida, custo, resultado)

        return finalizar


def _roteador(configuracao: dict, medidor: Medidor, transporte: Transporte | None) -> Roteador:
    if transporte is None:
        return Roteador(configuracao=configuracao, finalizar=medidor.finalizar_com(True))
    return Roteador(
        configuracao=configuracao,
        transporte=transporte,
        reservar=medidor.reservar_offline,
        finalizar=medidor.finalizar_com(False),
        falhar=lambda *args: None,
        verificar_ativo=lambda: None,
    )


def _aplica(caso, lote: Lote, entrada: Entrada) -> bool:
    if lote.vagas_reais:
        return caso.vagas_reais
    return entrada.tipo in caso.armadilhas


def _taxa(parte: int, total: int) -> float:
    return round(parte / total, 4) if total else 0.0


def _taxa_por_regra(execucoes: list[Execucao], config: ConfiguracaoAvaliacao) -> dict[str, float]:
    regras = [FALHA_ESQUEMA, *(r.value for r in Regra if r.value not in config.regras_fora)]
    regras.append(FALHA_PROIBIDO)
    regras += sorted({f for e in execucoes for f in e.falhas} - set(regras))
    total = len(execucoes)
    return {regra: _taxa(sum(regra not in e.falhas for e in execucoes), total) for regra in regras}


def avaliar(
    tier: str,
    lotes: list[Lote],
    config: ConfiguracaoAvaliacao,
    modelos: dict,
    agora: datetime,
    fabrica: FabricaTransporte | None = None,
    vagas_sem_conteudo: int = 0,
) -> dict:
    versao = versao_do_conjunto(config, lotes)
    em_avaliacao = configuracao_em_avaliacao(modelos, tier, versao, agora.date())
    dados_tier = modelos["tiers"][tier]
    casos = {
        nome: caso
        for nome, caso in config.casos.items()
        if caso.tarefa in dados_tier.get("uso", [])
    }
    for caso in casos.values():
        if caso.executor not in EXECUTORES:
            raise ValueError(f"executor de avaliacao desconhecido: {caso.executor}")
    medidor = Medidor()
    execucoes: list[Execucao] = []
    for nome, caso in casos.items():
        for lote in lotes:
            for entrada in lote.entradas:
                if not _aplica(caso, lote, entrada):
                    continue
                transporte = fabrica(entrada, lote.conteudo) if fabrica else None
                roteador = _roteador(em_avaliacao, medidor, transporte)
                executor = EXECUTORES[caso.executor]
                execucoes.append(
                    executor(entrada, lote.conteudo, roteador, nome, caso.tarefa, tier)
                )
    reais = [e for e in execucoes if e.entrada.tipo == config.vagas_reais.tipo]
    armadilhas = [e for e in execucoes if e.entrada.tipo != config.vagas_reais.tipo]
    exigidas = list(modelos.get("conjunto_avaliacao", {}).get("armadilhas", []))
    sem_cobertura = [tipo for tipo in exigidas if tipo not in {e.entrada.tipo for e in armadilhas}]
    falhas_por_armadilha = dict(Counter(e.entrada.tipo for e in armadilhas if not e.aprovada))
    taxa = _taxa(sum(e.aprovada for e in execucoes), len(execucoes))
    motivos = []
    if not execucoes:
        motivos.append("nenhum caso de prompt avaliado para o tier")
    if sem_cobertura:
        motivos.append("tipo de armadilha sem cobertura")
    if falhas_por_armadilha:
        motivos.append("armadilha com falha")
    if execucoes and taxa < config.taxa_minima_aprovacao:
        motivos.append("taxa de aprovacao abaixo do minimo")
    return {
        "data": agora.isoformat(),
        "tier": tier,
        "modo": "offline" if fabrica else "real",
        "provedor": dados_tier.get("provedor"),
        "modelo": dados_tier.get("modelo"),
        "versao_conjunto": versao,
        "versoes_prompt": {
            nome: sorted({e.versao_prompt for e in execucoes if e.caso == nome}) for nome in casos
        },
        "execucoes": len(execucoes),
        "taxa_aprovacao": taxa,
        "taxa_minima_aprovacao": config.taxa_minima_aprovacao,
        "taxa_por_regra": _taxa_por_regra(execucoes, config),
        "falhas_por_armadilha": falhas_por_armadilha,
        "armadilhas": [
            {
                "id": e.entrada.id,
                "tipo": e.entrada.tipo,
                "caso": e.caso,
                "aprovada": e.aprovada,
                "falhas": list(e.falhas),
            }
            for e in armadilhas
        ],
        "armadilhas_sem_cobertura": sem_cobertura,
        "vagas_reais": {
            "avaliadas": len(reais),
            "aprovadas": sum(e.aprovada for e in reais),
            "falhas": dict(Counter(f for e in reais for f in e.falhas)),
            "sem_conteudo": vagas_sem_conteudo,
        },
        "custo_usd": str(medidor.custo),
        "chamadas": medidor.chamadas,
        "veredito": REPROVADO if motivos else APROVADO,
        "motivos": motivos,
    }
