from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from src.coletor.contratos import ModeloTrabalho, Senioridade

SEPARADOR_DETALHE = ": "


class Motivo(StrEnum):
    DUPLICATA = "duplicata"
    FUNCAO = "funcao_fora_do_escopo"
    SENIORIDADE = "senioridade_recusada"
    TITULO = "titulo_recusado"
    ANOS = "anos_acima_do_maximo"
    MODELO = "modelo_recusado"
    PAIS = "pais_fora_do_escopo"
    LOCAL = "presencial_fora_da_regiao"
    IDADE = "vaga_antiga"
    PRE_NOTA = "pre_nota_abaixo_do_minimo"
    PONTUACAO_INVALIDA = "pontuacao_invalida"


def texto_do_motivo(motivo: Motivo, detalhe: str = "") -> str:
    return f"{motivo.value}{SEPARADOR_DETALHE}{detalhe}" if detalhe else motivo.value


def codigo_do_motivo(texto: str) -> str:
    return texto.split(SEPARADOR_DETALHE, 1)[0]


@dataclass(frozen=True, slots=True)
class VagaTriagem:
    id: int
    fonte: str
    empresa: str
    titulo: str
    url: str
    descricao: str = ""
    local: str = ""
    pais: str = ""
    alvo: bool = False
    senioridade: Senioridade = Senioridade.INDEFINIDA
    modelo: ModeloTrabalho = ModeloTrabalho.INDEFINIDO
    publicada_em: date | None = None


@dataclass(frozen=True, slots=True)
class VagaAguardando:
    vaga: VagaTriagem
    pre_nota: int
