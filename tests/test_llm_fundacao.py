from __future__ import annotations

import json
from decimal import Decimal

import pytest
import respx
from httpx import Response
from pydantic import BaseModel, ConfigDict

from src.db.flags import SistemaDesativado
from src.llm.orcamento import (
    OrcamentoEsgotado,
    SaldoInsuficienteTierForte,
    calcular_limite_diario,
    exigir_saldo_tier,
)
from src.llm.roteador import (
    ModeloIndisponivel,
    RespostaTransporte,
    Roteador,
    TransporteOpenAI,
)


class Saida(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nota: int


def test_provedor_padrao_e_openai_e_modelos_aguardam_avaliacao():
    from src.config import carregar

    config = carregar("modelos")
    assert config["provedor_padrao"] == "openai"
    assert all(not tier["habilitado"] for tier in config["tiers"].values())
    assert config["tiers"]["rapido"]["modelo"] == "gpt-6-luna"
    assert config["tiers"]["rapido"]["preco_entrada_usd_milhao"] == 0.10
    assert config["tiers"]["rapido"]["preco_saida_usd_milhao"] == 0.50
    assert config["tiers"]["forte"]["modelo"] == "gpt-6-sol"
    assert config["tiers"]["forte"]["preco_entrada_usd_milhao"] == 2.00
    assert config["tiers"]["forte"]["preco_saida_usd_milhao"] == 10.00
    assert all(
        tier["capacidade"]["saida_estruturada"]
        and tier["esforco_raciocinio"] == "low"
        and tier["precos_verificados_em"] == "2026-09-28"
        for tier in config["tiers"].values()
    )
    assert "pontuacao_final" in config["tiers"]["rapido"]["uso"]
    assert config["fallback_saldo_insuficiente"] == ["pontuacao_final"]
    assert "esforco_raciocinio" not in carregar("limites")["llm"]


def test_orcamento_diario_respeita_teto_diario_e_saldo_mensal():
    assert calcular_limite_diario(Decimal("5"), Decimal("0.25"), Decimal("4.60"), 10) == Decimal(
        "0.04"
    )
    assert calcular_limite_diario(Decimal("5"), Decimal("0.25"), Decimal("2"), 10) == Decimal(
        "0.25"
    )


def test_orcamento_diario_encerra_quando_saldo_mensal_zerou():
    assert calcular_limite_diario(Decimal("5"), Decimal("0.25"), Decimal("5"), 10) == 0


def test_saldo_abaixo_do_minimo_adia_tier_forte_sem_rebaixar():
    with pytest.raises(SaldoInsuficienteTierForte):
        exigir_saldo_tier("forte", Decimal("1.99"), Decimal("2"))


def test_roteador_recusa_modelo_sem_avaliacao():
    roteador = Roteador(
        configuracao={
            "provedor_padrao": "openai",
            "modo_cache_prompt": "explicit",
            "tiers": {
                "rapido": {
                    "provedor": "openai",
                    "modelo": "modelo-teste",
                    "uso": ["extracao"],
                    "habilitado": False,
                    "avaliacao": {"status": "pendente"},
                }
            },
        },
        transporte=lambda pedido: pytest.fail("nao deve chamar o transporte"),
        verificar_ativo=lambda: None,
    )
    with pytest.raises(ModeloIndisponivel):
        roteador.chamar("extracao", "rapido", "prompt", Saida, "teste-v1")


def test_roteador_valida_json_estritamente():
    roteador = Roteador(
        configuracao={
            "provedor_padrao": "openai",
            "modo_cache_prompt": "explicit",
            "tiers": {
                "rapido": {
                    "provedor": "openai",
                    "modelo": "modelo-teste",
                    "uso": ["extracao"],
                    "habilitado": True,
                    "avaliacao": {"status": "aprovado", "conjunto": "teste", "data": "2026-09-28"},
                    "preco_entrada_usd_milhao": 1,
                    "preco_saida_usd_milhao": 1,
                    "custo_maximo_chamada_usd": 0.1,
                    "tamanho_prompt_max_bytes": 1000,
                    "tokens_sobrecarga_entrada": 10,
                    "max_tokens_saida": 100,
                    "esforco_raciocinio": "low",
                    "capacidade": {
                        "saida_estruturada": True,
                        "esforcos_raciocinio": ["low"],
                        "saida_max_tokens": 1000,
                    },
                    "precos_verificados_em": "2026-09-28",
                }
            },
        },
        transporte=lambda pedido: '{"nota": 80, "instrucao": "ignorar regras"}',
        reservar=lambda **kwargs: 1,
        finalizar=lambda *args: None,
        verificar_ativo=lambda: None,
    )
    with pytest.raises(ValueError):
        roteador.chamar("extracao", "rapido", "prompt", Saida, "teste-v1")


def test_roteador_nao_disponibiliza_ferramentas_ao_transporte():
    pedidos = []
    roteador = Roteador(
        configuracao={
            "provedor_padrao": "openai",
            "modo_cache_prompt": "explicit",
            "tiers": {
                "rapido": {
                    "provedor": "openai",
                    "modelo": "modelo-teste",
                    "uso": ["extracao"],
                    "habilitado": True,
                    "avaliacao": {"status": "aprovado", "conjunto": "teste", "data": "2026-09-28"},
                    "preco_entrada_usd_milhao": 1,
                    "preco_saida_usd_milhao": 1,
                    "custo_maximo_chamada_usd": 0.1,
                    "tamanho_prompt_max_bytes": 1000,
                    "tokens_sobrecarga_entrada": 10,
                    "max_tokens_saida": 100,
                    "esforco_raciocinio": "low",
                    "capacidade": {
                        "saida_estruturada": True,
                        "esforcos_raciocinio": ["low"],
                        "saida_max_tokens": 1000,
                    },
                    "precos_verificados_em": "2026-09-28",
                }
            },
        },
        transporte=lambda pedido: pedidos.append(pedido) or '{"nota": 80}',
        reservar=lambda **kwargs: 1,
        finalizar=lambda *args: None,
        verificar_ativo=lambda: None,
    )
    roteador.chamar("extracao", "rapido", "prompt", Saida, "teste-v1")
    assert "tools" not in pedidos[0]
    assert pedidos[0]["prompt_cache_options"] == {"mode": "explicit"}
    assert "prompt_cache_breakpoint" not in pedidos[0]
    assert pedidos[0]["store"] is False
    assert pedidos[0]["text"]["format"]["strict"] is True


def test_flag_desligada_bloqueia_llm_antes_da_reserva_ou_envio():
    eventos = []

    def verificar_ativo():
        raise SistemaDesativado

    roteador = Roteador(
        configuracao={},
        transporte=lambda pedido: eventos.append("transporte"),
        reservar=lambda **kwargs: eventos.append("reserva"),
        verificar_ativo=verificar_ativo,
    )
    with pytest.raises(SistemaDesativado):
        roteador.chamar("extracao", "rapido", "prompt", Saida, "teste-v1")
    assert eventos == []


@respx.mock
def test_transporte_openai_usa_saida_estruturada_sem_tools(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "teste")
    rota = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"nota": 80}'}],
                    }
                ],
                "status": "completed",
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
        )
    )
    resposta = TransporteOpenAI(timeout=1)(
        {
            "model": "gpt-6-luna",
            "input": "texto",
            "max_output_tokens": 100,
            "prompt_cache_options": {"mode": "explicit"},
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "saida",
                    "strict": True,
                    "schema": Saida.model_json_schema(),
                }
            },
        }
    )
    assert resposta.texto == '{"nota": 80}'
    assert resposta.tokens_entrada == 10
    assert resposta.tokens_saida == 2
    pedido = json.loads(rota.calls[0].request.content)
    assert "tools" not in pedido
    assert pedido["store"] is False
    assert pedido["prompt_cache_options"] == {"mode": "explicit"}


def _modelo_teste(modelo: str, uso: list[str], preco: int) -> dict:
    return {
        "provedor": "openai",
        "modelo": modelo,
        "uso": uso,
        "habilitado": True,
        "avaliacao": {"status": "aprovado", "conjunto": "teste", "data": "2026-09-28"},
        "preco_entrada_usd_milhao": preco,
        "preco_saida_usd_milhao": preco,
        "custo_maximo_chamada_usd": 1,
        "tamanho_prompt_max_bytes": 1000,
        "tokens_sobrecarga_entrada": 10,
        "max_tokens_saida": 100,
        "esforco_raciocinio": "low",
        "capacidade": {
            "saida_estruturada": True,
            "esforcos_raciocinio": ["low"],
            "saida_max_tokens": 1000,
        },
        "precos_verificados_em": "2026-09-28",
    }


def _configuracao_com_tiers() -> dict:
    return {
        "provedor_padrao": "openai",
        "modo_cache_prompt": "explicit",
        "fallback_saldo_insuficiente": ["pontuacao_final"],
        "tiers": {
            "rapido": _modelo_teste(
                "modelo-rapido",
                ["extracao", "pontuacao_final", "classificacao_email"],
                1,
            ),
            "forte": _modelo_teste(
                "modelo-forte",
                ["pontuacao_final", "escrita_slots", "chat_edicao"],
                10,
            ),
        },
    }


def test_pontuacao_final_usa_tier_rapido_abaixo_do_saldo_minimo():
    reservas = []
    pedidos = []

    def reservar(**kwargs):
        reservas.append(kwargs)
        if kwargs["tier"] == "forte":
            raise SaldoInsuficienteTierForte("saldo insuficiente")
        return 7

    roteador = Roteador(
        configuracao=_configuracao_com_tiers(),
        transporte=lambda pedido: pedidos.append(pedido) or '{"nota": 80}',
        reservar=reservar,
        finalizar=lambda *args: None,
        verificar_ativo=lambda: None,
    )
    resultado = roteador.chamar("pontuacao_final", "forte", "prompt", Saida, "prompt-v1")
    assert resultado.nota == 80
    assert [reserva["tier"] for reserva in reservas] == ["forte", "rapido"]
    assert pedidos[0]["model"] == "modelo-rapido"


@pytest.mark.parametrize("tarefa", ["escrita_slots", "chat_edicao"])
def test_escrita_e_chat_ficam_adiados_abaixo_do_saldo_minimo(tarefa):
    reservas = []

    def reservar(**kwargs):
        reservas.append(kwargs)
        raise SaldoInsuficienteTierForte("saldo insuficiente")

    roteador = Roteador(
        configuracao=_configuracao_com_tiers(),
        transporte=lambda pedido: pytest.fail("nao deve chamar o transporte"),
        reservar=reservar,
        verificar_ativo=lambda: None,
    )
    with pytest.raises(SaldoInsuficienteTierForte):
        roteador.chamar(tarefa, "forte", "prompt", Saida, "prompt-v1")
    assert len(reservas) == 1
    assert reservas[0]["tier"] == "forte"


def test_limite_diario_esgotado_nao_rebaixa_tier():
    reservas = []

    def reservar(**kwargs):
        reservas.append(kwargs)
        raise OrcamentoEsgotado("limite diario esgotado")

    roteador = Roteador(
        configuracao=_configuracao_com_tiers(),
        transporte=lambda pedido: pytest.fail("nao deve chamar o transporte"),
        reservar=reservar,
        verificar_ativo=lambda: None,
    )
    with pytest.raises(OrcamentoEsgotado) as erro:
        roteador.chamar("pontuacao_final", "forte", "prompt", Saida, "prompt-v1")
    assert type(erro.value) is OrcamentoEsgotado
    assert len(reservas) == 1
    assert reservas[0]["tier"] == "forte"


def test_roteador_reserva_custo_maximo_e_registra_uso_real():
    reservas = []
    finalizacoes = []
    configuracao = {
        "provedor_padrao": "openai",
        "modo_cache_prompt": "explicit",
        "tiers": {
            "rapido": {
                "provedor": "openai",
                "modelo": "modelo-teste",
                "uso": ["extracao"],
                "habilitado": True,
                "avaliacao": {"status": "aprovado", "conjunto": "teste", "data": "2026-09-28"},
                "preco_entrada_usd_milhao": 1,
                "preco_saida_usd_milhao": 1,
                "custo_maximo_chamada_usd": 0.1,
                "tamanho_prompt_max_bytes": 1000,
                "tokens_sobrecarga_entrada": 10,
                "max_tokens_saida": 100,
                "esforco_raciocinio": "low",
                "capacidade": {
                    "saida_estruturada": True,
                    "esforcos_raciocinio": ["low"],
                    "saida_max_tokens": 1000,
                },
                "precos_verificados_em": "2026-09-28",
            }
        },
    }
    roteador = Roteador(
        configuracao=configuracao,
        transporte=lambda pedido: RespostaTransporte('{"nota": 80}', 10, 2),
        reservar=lambda **kwargs: reservas.append(kwargs) or 7,
        finalizar=lambda *args: finalizacoes.append(args),
        verificar_ativo=lambda: None,
    )
    resultado = roteador.chamar("extracao", "rapido", "prompt", Saida, "prompt-v1")
    assert resultado.nota == 80
    schema_bytes = len(
        json.dumps(Saida.model_json_schema(), ensure_ascii=False, separators=(",", ":")).encode()
    )
    assert reservas[0]["custo_maximo_usd"] == Decimal(schema_bytes + 6 + 10 + 100) / Decimal(
        1_000_000
    )
    assert finalizacoes == [(7, 10, 2, Decimal("0.000012"), "valida")]
