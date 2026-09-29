from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TypeVar

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from src.config import carregar
from src.db.flags import exigir_sistema_ativo
from src.db.uso_llm import falhar_uso_llm, finalizar_uso_llm, reservar_uso_llm
from src.llm.orcamento import SaldoInsuficienteTierForte

T = TypeVar("T", bound=BaseModel)


class ModeloIndisponivel(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RespostaTransporte:
    texto: str
    tokens_entrada: int = 0
    tokens_saida: int = 0


class TransporteOpenAI:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def __call__(self, pedido: dict[str, object]) -> RespostaTransporte:
        load_dotenv()
        chave = os.getenv("OPENAI_API_KEY")
        if not chave:
            raise ModeloIndisponivel("OPENAI_API_KEY ausente")
        with httpx.Client(timeout=self.timeout) as cliente:
            resposta = cliente.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {chave}"},
                json=pedido,
            )
        resposta.raise_for_status()
        conteudo = resposta.json()
        if (
            not isinstance(conteudo, dict)
            or conteudo.get("status") != "completed"
            or not isinstance(conteudo.get("output"), list)
        ):
            raise ValueError("resposta da OpenAI sem lista de saida")
        textos = []
        for item in conteudo.get("output", []):
            if not isinstance(item, dict):
                raise ValueError("item de saida da OpenAI invalido")
            if item.get("type") != "message":
                continue
            partes = item.get("content")
            if not isinstance(partes, list):
                raise ValueError("conteudo de saida da OpenAI invalido")
            for parte in partes:
                if not isinstance(parte, dict):
                    raise ValueError("conteudo de saida da OpenAI invalido")
                if parte.get("type") == "refusal":
                    raise ValueError("provedor recusou a solicitacao")
                if parte.get("type") == "output_text":
                    texto = parte.get("text")
                    if not isinstance(texto, str):
                        raise ValueError("texto da resposta OpenAI invalido")
                    textos.append(texto)
        texto = "".join(textos)
        if not texto:
            raise ValueError("resposta estruturada vazia")
        uso = conteudo.get("usage")
        if not isinstance(uso, dict) or "input_tokens" not in uso or "output_tokens" not in uso:
            raise ValueError("resposta da OpenAI sem contagem de tokens")
        tokens_entrada = int(uso["input_tokens"])
        tokens_saida = int(uso["output_tokens"])
        if min(tokens_entrada, tokens_saida) < 0:
            raise ValueError("contagem de tokens invalida")
        return RespostaTransporte(
            texto=texto,
            tokens_entrada=tokens_entrada,
            tokens_saida=tokens_saida,
        )


class Roteador:
    def __init__(
        self,
        configuracao: dict | None = None,
        transporte: Callable[[dict[str, object]], RespostaTransporte | str] | None = None,
        reservar: Callable[..., int] | None = None,
        finalizar: Callable[..., None] | None = None,
        falhar: Callable[..., None] | None = None,
        verificar_ativo: Callable[[], None] | None = None,
    ) -> None:
        self.configuracao = configuracao if configuracao is not None else carregar("modelos")
        limites = carregar("limites")
        self.transporte = transporte or TransporteOpenAI(
            timeout=float(limites["rede"]["timeout_s"])
        )
        self.reservar = reservar or reservar_uso_llm
        self.finalizar = finalizar or finalizar_uso_llm
        self.falhar = falhar or falhar_uso_llm
        self.verificar_ativo = verificar_ativo or exigir_sistema_ativo

    def chamar(
        self, tarefa: str, tier: str, prompt: str, esquema: type[T], versao_prompt: str
    ) -> T:
        self.verificar_ativo()
        modelo = self._modelo(tarefa, tier)
        if not prompt.strip() or not versao_prompt.strip():
            raise ValueError("prompt e versao sao obrigatorios")
        schema = esquema.model_json_schema()
        custo_maximo = self._custo_maximo(modelo, prompt, schema)
        try:
            uso_id = self.reservar(
                etapa=tarefa,
                provedor=modelo["provedor"],
                modelo=modelo["modelo"],
                tier=tier,
                prompt_versao=versao_prompt,
                custo_maximo_usd=custo_maximo,
            )
        except SaldoInsuficienteTierForte:
            tarefas_fallback = self.configuracao.get("fallback_saldo_insuficiente", [])
            if tier != "forte" or tarefa not in tarefas_fallback:
                raise
            tier = "rapido"
            modelo = self._modelo(tarefa, tier)
            custo_maximo = self._custo_maximo(modelo, prompt, schema)
            uso_id = self.reservar(
                etapa=tarefa,
                provedor=modelo["provedor"],
                modelo=modelo["modelo"],
                tier=tier,
                prompt_versao=versao_prompt,
                custo_maximo_usd=custo_maximo,
            )
        pedido = {
            "model": modelo["modelo"],
            "input": prompt,
            "max_output_tokens": int(modelo["max_tokens_saida"]),
            "prompt_cache_options": {"mode": "explicit"},
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "saida_estruturada",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if modelo.get("esforco_raciocinio"):
            pedido["reasoning"] = {"effort": modelo["esforco_raciocinio"]}
        try:
            resposta_bruta = self.transporte(pedido)
        except (httpx.HTTPError, ModeloIndisponivel, ValueError) as exc:
            self.falhar(uso_id, type(exc).__name__)
            raise
        resposta = (
            resposta_bruta
            if isinstance(resposta_bruta, RespostaTransporte)
            else RespostaTransporte(texto=resposta_bruta)
        )
        custo = (
            Decimal(resposta.tokens_entrada)
            * Decimal(str(modelo["preco_entrada_usd_milhao"]))
            + Decimal(resposta.tokens_saida) * Decimal(str(modelo["preco_saida_usd_milhao"]))
        ) / Decimal(1_000_000)
        try:
            dados = json.loads(
                resposta.texto,
                object_pairs_hook=self._sem_chaves_duplicadas,
                parse_constant=self._recusar_constante,
            )
            resultado = esquema.model_validate(dados, strict=True)
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
            self.finalizar(
                uso_id,
                resposta.tokens_entrada,
                resposta.tokens_saida,
                custo,
                "invalida",
            )
            raise
        self.finalizar(
            uso_id,
            resposta.tokens_entrada,
            resposta.tokens_saida,
            custo,
            "valida",
        )
        return resultado

    def _modelo(self, tarefa: str, tier: str) -> dict:
        tiers = self.configuracao.get("tiers", {})
        if tier not in tiers:
            raise ModeloIndisponivel(f"tier desconhecido: {tier}")
        modelo = tiers[tier]
        avaliacao = modelo.get("avaliacao") or {}
        if (
            self.configuracao.get("provedor_padrao") != "openai"
            or self.configuracao.get("modo_cache_prompt") != "explicit"
            or modelo.get("provedor") != "openai"
            or not modelo.get("habilitado")
            or avaliacao.get("status") != "aprovado"
            or not avaliacao.get("conjunto")
            or not avaliacao.get("data")
            or not modelo.get("modelo")
            or tarefa not in modelo.get("uso", [])
        ):
            raise ModeloIndisponivel(f"modelo nao avaliado ou habilitado para {tarefa}")
        capacidade = modelo.get("capacidade") or {}
        if not capacidade.get("saida_estruturada"):
            raise ModeloIndisponivel("modelo nao garante saida estruturada")
        if modelo.get("esforco_raciocinio") not in capacidade.get("esforcos_raciocinio", []):
            raise ModeloIndisponivel("esforco de raciocinio nao suportado pelo modelo")
        try:
            date.fromisoformat(avaliacao["data"])
            date.fromisoformat(modelo["precos_verificados_em"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ModeloIndisponivel("avaliacao ou precos sem data valida") from exc
        campos_necessarios = (
            "preco_entrada_usd_milhao",
            "preco_saida_usd_milhao",
            "custo_maximo_chamada_usd",
            "tamanho_prompt_max_bytes",
            "tokens_sobrecarga_entrada",
            "max_tokens_saida",
        )
        if any(modelo.get(campo) is None for campo in campos_necessarios):
            raise ModeloIndisponivel("preco e limites oficiais do modelo nao configurados")
        if (
            int(modelo["tamanho_prompt_max_bytes"]) <= 0
            or int(modelo["tokens_sobrecarga_entrada"]) < 0
        ):
            raise ModeloIndisponivel("limite de prompt invalido")
        if int(modelo["max_tokens_saida"]) <= 0:
            raise ModeloIndisponivel("limite de saida invalido")
        if (
            modelo["preco_entrada_usd_milhao"] <= 0
            or modelo["preco_saida_usd_milhao"] <= 0
            or modelo["custo_maximo_chamada_usd"] <= 0
        ):
            raise ModeloIndisponivel("precos e custos precisam ser positivos")
        if (
            capacidade.get("saida_max_tokens") is None
            or int(modelo["max_tokens_saida"]) > int(capacidade["saida_max_tokens"])
        ):
            raise ModeloIndisponivel("saida excede a capacidade documentada do modelo")
        return modelo

    @staticmethod
    def _custo_maximo(modelo: dict, prompt: str, schema: dict) -> Decimal:
        tamanho_prompt = len(prompt.encode("utf-8")) + len(
            json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        if tamanho_prompt > int(modelo["tamanho_prompt_max_bytes"]):
            raise ValueError("prompt excede o limite configurado para o modelo")
        tokens_entrada_reservados = tamanho_prompt + int(modelo["tokens_sobrecarga_entrada"])
        custo_maximo = (
            Decimal(tokens_entrada_reservados)
            * Decimal(str(modelo["preco_entrada_usd_milhao"]))
            + Decimal(int(modelo["max_tokens_saida"]))
            * Decimal(str(modelo["preco_saida_usd_milhao"]))
        ) / Decimal(1_000_000)
        if custo_maximo > Decimal(str(modelo["custo_maximo_chamada_usd"])):
            raise ValueError("custo maximo da chamada excede o limite configurado")
        return custo_maximo

    @staticmethod
    def _sem_chaves_duplicadas(pares: list[tuple[str, object]]) -> dict[str, object]:
        objeto = {}
        for chave, valor in pares:
            if chave in objeto:
                raise ValueError("JSON com chave duplicada")
            objeto[chave] = valor
        return objeto

    @staticmethod
    def _recusar_constante(valor: str) -> None:
        raise ValueError(f"constante JSON invalida: {valor}")
