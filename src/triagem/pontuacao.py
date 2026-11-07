from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import Field, StringConstraints, ValidationError, create_model

from src.conteudo.modelo import Estrito, Inventario
from src.llm.roteador import Roteador
from src.padroes.configuracao import ConfiguracaoPadroes
from src.triagem.configuracao import ConfiguracaoTriagem
from src.triagem.contratos import VagaTriagem
from src.triagem.prompt import montar_prompt_de_pontuacao

ORIGEM_MODELO = "modelo"
ORIGEM_CACHE = "cache"
NOTA_MAXIMA = 100


class PontuacaoInvalida(ValueError):
    def __init__(self, codigo: str, chamou_modelo: bool = False) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.chamou_modelo = chamou_modelo


class RepositorioDeCache(Protocol):
    def resultado_em_cache(self, hash_entrada: str) -> dict | None: ...


@dataclass(frozen=True, slots=True)
class ResultadoDaPontuacao:
    nota: int
    registro: dict
    origem: str


def _texto(max_chars: int) -> type:
    return Annotated[str, StringConstraints(min_length=1, max_length=max_chars)]


def esquema_da_pontuacao(
    config: ConfiguracaoTriagem, padroes: ConfiguracaoPadroes
) -> type[Estrito]:
    regras = config.pontuacao_final
    equivalente = create_model(
        "TechEquivalente",
        __base__=Estrito,
        pedida=(_texto(regras.tech_max_chars), ...),
        equivalente=(_texto(regras.tech_max_chars), ...),
    )
    techs = Annotated[list[_texto(regras.tech_max_chars)], Field(max_length=regras.techs_max)]
    requisitos = Annotated[
        list[_texto(regras.requisito_max_chars)], Field(max_length=regras.requisitos_max)
    ]
    return create_model(
        "PontuacaoDaVaga",
        __base__=Estrito,
        familia=(Literal[tuple(padroes.foco_sobre)], ...),
        idioma=(Literal[tuple(padroes.idiomas)], ...),
        nota_aderencia=(Annotated[int, Field(ge=0, le=NOTA_MAXIMA)], ...),
        techs_cobertas=(techs, ...),
        techs_equivalentes=(
            Annotated[list[equivalente], Field(max_length=regras.techs_max)],
            ...,
        ),
        requisitos_descobertos=(requisitos, ...),
        alertas=(Annotated[list[Literal[tuple(regras.alertas)]], Field(max_length=10)], ...),
        justificativa=(_texto(regras.justificativa_max_chars), ...),
    )


def _conferir_com_o_inventario(dados: dict, inventario: Inventario) -> None:
    permitidas = {item.tech for item in inventario.techs}
    if not set(dados["techs_cobertas"]) <= permitidas:
        raise PontuacaoInvalida("tech_fora_do_inventario")
    tabela = {(e.pedido, e.tem) for e in inventario.equivalencias}
    pares = {(par["pedida"], par["equivalente"]) for par in dados["techs_equivalentes"]}
    if not pares <= tabela:
        raise PontuacaoInvalida("equivalencia_fora_da_tabela")


def _texto_suspeito(vaga: VagaTriagem, config: ConfiguracaoTriagem) -> bool:
    texto = f"{vaga.titulo}\n{vaga.descricao}"
    return any(
        re.search(padrao, texto, re.IGNORECASE) for padrao in config.pontuacao_final.padroes_injecao
    )


def _validar(esquema: type[Estrito], bruto: dict, inventario: Inventario) -> dict:
    try:
        dados = esquema.model_validate(bruto).model_dump()
    except ValidationError as erro:
        raise PontuacaoInvalida("resposta_fora_do_schema") from erro
    _conferir_com_o_inventario(dados, inventario)
    return dados


def pontuar_vaga(
    vaga: VagaTriagem,
    inventario: Inventario,
    roteador: Roteador,
    repositorio: RepositorioDeCache,
    config: ConfiguracaoTriagem,
    padroes: ConfiguracaoPadroes,
) -> ResultadoDaPontuacao:
    regras = config.pontuacao_final
    prompt = montar_prompt_de_pontuacao(vaga, inventario, config, padroes)
    esquema = esquema_da_pontuacao(config, padroes)
    guardado = repositorio.resultado_em_cache(prompt.sha256_entrada)
    if guardado is not None:
        dados = _validar(esquema, guardado, inventario)
        origem = ORIGEM_CACHE
    else:
        versao = f"pontuar_vaga_v{prompt.versao}_{prompt.sha256_modelo[:12]}"
        try:
            resposta = roteador.chamar(regras.tarefa, regras.tier, prompt.texto, esquema, versao)
        except ValueError as erro:
            raise PontuacaoInvalida("resposta_invalida", chamou_modelo=True) from erro
        try:
            dados = _validar(esquema, resposta.model_dump(), inventario)
        except PontuacaoInvalida as erro:
            erro.chamou_modelo = True
            raise
        origem = ORIGEM_MODELO
    if _texto_suspeito(vaga, config) and regras.alerta_texto_suspeito not in dados["alertas"]:
        dados["alertas"] = [*dados["alertas"], regras.alerta_texto_suspeito]
    registro = {
        "hash_entrada": prompt.sha256_entrada,
        "prompt_versao": prompt.versao,
        "prompt_sha256": prompt.sha256_modelo,
        "origem": origem,
        "resultado": dados,
    }
    return ResultadoDaPontuacao(nota=dados["nota_aderencia"], registro=registro, origem=origem)
