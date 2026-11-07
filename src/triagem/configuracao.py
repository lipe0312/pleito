from __future__ import annotations

from functools import lru_cache
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.coletor.contratos import Funcao, ModeloTrabalho, Senioridade
from src.config import carregar
from src.conteudo.modelo import Estrito

PASTA_DOS_PROMPTS = "prompts"


class Tolerante(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Pesos(Estrito):
    peso_stack: int = Field(ge=0)
    peso_senioridade: int = Field(ge=0)
    peso_modelo: int = Field(ge=0)
    peso_pais: int = Field(ge=0)
    peso_empresa_alvo: int = Field(ge=0)
    peso_recencia: int = Field(ge=0)

    @model_validator(mode="after")
    def _soma_positiva(self) -> Pesos:
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("pesos da pre-nota precisam somar mais que zero")
        return self


class Eliminatorios(Tolerante):
    exige_anos_experiencia_max: int
    recusa_titulos_com: list[str]
    recusa_se_exige_presencial_fora_de: list[str]
    idade_maxima_dias: int
    funcoes_aceitas: list[Funcao]


class Filtros(Tolerante):
    senioridades_recusadas: list[Senioridade]
    modelos_aceitos: list[ModeloTrabalho]
    paises_aceitos: list[str]
    eliminatorios: Eliminatorios
    pontuacao: Pesos


class Normalizacao(Estrito):
    parametros_rastreio_prefixos: list[str]
    parametros_rastreio: list[str]


class PreNota(Estrito):
    senioridade: dict[Senioridade, float]
    modelo: dict[ModeloTrabalho, float]
    pais: dict[str, float]
    pais_outro: float = Field(ge=0, le=1)
    pais_ausente: float = Field(ge=0, le=1)
    recencia_sem_data: float = Field(ge=0, le=1)
    equivalente_peso: float = Field(ge=0, le=1)
    techs_para_nota_cheia: int = Field(gt=0)
    techs_fora_do_inventario: list[str]

    @model_validator(mode="after")
    def _fracoes_entre_zero_e_um(self) -> PreNota:
        fracoes = [*self.senioridade.values(), *self.modelo.values(), *self.pais.values()]
        if any(fracao < 0 or fracao > 1 for fracao in fracoes):
            raise ValueError("fracao da pre-nota precisa estar entre 0 e 1")
        return self


class PontuacaoFinal(Estrito):
    tarefa: str
    tier: str
    prompt: str
    titulo_max_chars: int = Field(gt=0)
    techs_max: int = Field(gt=0)
    tech_max_chars: int = Field(gt=0)
    requisitos_max: int = Field(gt=0)
    requisito_max_chars: int = Field(gt=0)
    justificativa_max_chars: int = Field(gt=0)
    alertas: list[str] = Field(min_length=1)
    alerta_texto_suspeito: str
    padroes_injecao: list[str]

    @model_validator(mode="after")
    def _prompt_na_pasta_e_alerta_declarado(self) -> PontuacaoFinal:
        partes = PurePosixPath(self.prompt).parts
        if len(partes) != 2 or partes[0] != PASTA_DOS_PROMPTS or partes[1] in {"..", "."}:
            raise ValueError(f"prompt precisa estar direto em {PASTA_DOS_PROMPTS}/")
        if self.alerta_texto_suspeito not in self.alertas:
            raise ValueError("alerta de texto suspeito precisa estar em alertas")
        return self


class ConfiguracaoTriagem(Estrito):
    filtros: Filtros
    normalizacao: Normalizacao
    pre_nota: PreNota
    pontuacao_final: PontuacaoFinal
    pre_pontuadas_max: int = Field(gt=0)
    pre_nota_minima: int = Field(ge=0, le=100)
    descricao_max_chars: int = Field(gt=0)


@lru_cache(maxsize=1)
def configuracao_triagem() -> ConfiguracaoTriagem:
    triagem = carregar("triagem")
    limites = carregar("limites")
    return ConfiguracaoTriagem(
        filtros=Filtros.model_validate(carregar("filtros")),
        normalizacao=Normalizacao.model_validate(triagem["normalizacao"]),
        pre_nota=PreNota.model_validate(triagem["pre_nota"]),
        pontuacao_final=PontuacaoFinal.model_validate(triagem["pontuacao_final"]),
        pre_pontuadas_max=limites["diarios"]["vagas_pre_pontuadas_max"],
        pre_nota_minima=limites["llm"]["pre_nota_minima_para_forte"],
        descricao_max_chars=limites["llm"]["descricao_max_chars"],
    )
