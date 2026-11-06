from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from src.config import carregar
from src.conteudo.modelo import Estrito, Identificador
from src.padroes.erros import FamiliaDesconhecida, IdiomaDesconhecido

Fragmento = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
Lista = Annotated[list[Fragmento], Field(min_length=1)]
PorIdioma = dict[Identificador, Lista]
NomeCriterio = Literal[
    "cobertura_techs",
    "aderencia_familia",
    "verbo_repetido",
    "bullet_vago",
    "sobre_generico",
]
TOLERANCIA_DOS_PESOS = 6
PASTA_DOS_PROMPTS = "prompts"


class Faixa(Estrito):
    minimo: int = Field(ge=0)
    maximo: int = Field(gt=0)

    @model_validator(mode="after")
    def _minimo_nao_passa_do_maximo(self) -> Faixa:
        if self.minimo > self.maximo:
            raise ValueError("minimo maior que maximo")
        return self


class ConfiguracaoPrompt(Estrito):
    arquivo: Fragmento

    @model_validator(mode="after")
    def _arquivo_fica_na_pasta_dos_prompts(self) -> ConfiguracaoPrompt:
        partes = PurePosixPath(self.arquivo).parts
        if len(partes) != 2 or partes[0] != PASTA_DOS_PROMPTS or partes[1] in {"..", "."}:
            raise ValueError(f"arquivo do prompt precisa estar direto em {PASTA_DOS_PROMPTS}/")
        return self


class Marcacao(Estrito):
    abre: Fragmento
    fecha: Fragmento
    neutro: Fragmento
    vaga_max_chars: int = Field(gt=0)

    @model_validator(mode="after")
    def _neutro_nao_contem_marca(self) -> Marcacao:
        if self.abre in self.neutro or self.fecha in self.neutro:
            raise ValueError("texto neutro nao pode conter a marcacao")
        return self


class SenioridadeInflada(Estrito):
    verbos: PorIdioma
    expressoes: PorIdioma


class ConfiguracaoBullet(Estrito):
    formula: Fragmento
    chars: Faixa
    techs: Faixa


class ConfiguracaoSobre(Estrito):
    chars: Faixa
    techs_minimo: int = Field(ge=0)
    frases_vazias: PorIdioma


class Pontuacao(Estrito):
    terminador_bullet: str
    separador_interno: Fragmento
    proibidos: Lista


class Criterio(Estrito):
    peso: float = Field(gt=0, le=1)
    descricao: Fragmento


class Rubrica(Estrito):
    nota_minima: float = Field(ge=0, le=1)
    aderencia_termos_alvo: int = Field(gt=0)
    criterios: dict[NomeCriterio, Criterio]

    @model_validator(mode="after")
    def _criterios_completos_e_pesos_somam_um(self) -> Rubrica:
        faltando = set(NomeCriterio.__args__) - set(self.criterios)
        if faltando:
            raise ValueError(f"criterio da rubrica faltando: {sorted(faltando)}")
        total = sum(criterio.peso for criterio in self.criterios.values())
        if round(total, TOLERANCIA_DOS_PESOS) != 1:
            raise ValueError(f"pesos da rubrica precisam somar 1, somam {total}")
        return self


class ConfiguracaoPadroes(Estrito):
    idiomas: Annotated[list[Identificador], Field(min_length=1)]
    prompt: ConfiguracaoPrompt
    marcacao: Marcacao
    nao_invencao: Lista
    verbos_abertura_aceitos: PorIdioma
    aberturas_vagas: PorIdioma
    termos_vagos: PorIdioma
    senioridade_inflada: SenioridadeInflada
    bullet: ConfiguracaoBullet
    sobre: ConfiguracaoSobre
    termos_em_ingles_na_versao_pt: Lista
    pontuacao: Pontuacao
    foco_sobre: Annotated[dict[Identificador, PorIdioma], Field(min_length=1)]
    ordem_secoes: Lista
    secoes_proibidas: Lista
    ordem_de_corte: Lista
    nunca_no_corte: Lista
    rubrica: Rubrica

    @model_validator(mode="after")
    def _todo_idioma_declarado_em_toda_lista(self) -> ConfiguracaoPadroes:
        esperado = set(self.idiomas)
        por_idioma = [
            self.verbos_abertura_aceitos,
            self.aberturas_vagas,
            self.termos_vagos,
            self.senioridade_inflada.verbos,
            self.senioridade_inflada.expressoes,
            self.sobre.frases_vazias,
            *self.foco_sobre.values(),
        ]
        if any(set(lista) != esperado for lista in por_idioma):
            raise ValueError(f"toda lista por idioma precisa dos idiomas {sorted(esperado)}")
        return self

    def exigir(self, idioma: str, familia: str) -> None:
        if idioma not in self.idiomas:
            raise IdiomaDesconhecido(f"idioma fora de {self.idiomas}: {idioma!r}")
        if familia not in self.foco_sobre:
            raise FamiliaDesconhecida(f"familia fora de {sorted(self.foco_sobre)}: {familia!r}")


def configuracao_padroes(dados: dict | None = None) -> ConfiguracaoPadroes:
    return ConfiguracaoPadroes.model_validate(
        dados if dados is not None else carregar("padroes_curriculo")
    )
