from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Regra(StrEnum):
    PAGINAS = "paginas"
    TECNOLOGIA = "tecnologia"
    TRAVESSAO = "travessao"
    LATEX = "latex"
    CARACTERE_INVISIVEL = "caractere_invisivel"
    ALFABETO = "alfabeto"
    PREAMBULO = "preambulo"
    CABECALHO = "cabecalho"
    EXPERIENCIAS = "experiencias"
    EXPERIENCIA_VAZIA = "experiencia_vazia"
    NUMERO = "numero"
    EMPRESA_DA_VAGA = "empresa_da_vaga"
    COPIA_DA_VAGA = "copia_da_vaga"
    ESTRUTURA = "estrutura"
    PROJETOS = "projetos"
    ESCAPE = "escape"
    IDIOMA = "idioma"
    PONTUACAO = "pontuacao"
    SENIORIDADE = "senioridade"


CODIGOS = {
    Regra.PAGINAS: "V2",
    Regra.PREAMBULO: "V6",
    Regra.CABECALHO: "V7",
    Regra.EXPERIENCIAS: "V8",
    Regra.EXPERIENCIA_VAZIA: "V9",
    Regra.TECNOLOGIA: "V10",
    Regra.NUMERO: "V11",
    Regra.EMPRESA_DA_VAGA: "V12",
    Regra.COPIA_DA_VAGA: "V13",
    Regra.ESTRUTURA: "V14",
    Regra.PROJETOS: "V15",
    Regra.ESCAPE: "V16",
    Regra.LATEX: "V17",
    Regra.IDIOMA: "V19",
    Regra.PONTUACAO: "V20",
    Regra.SENIORIDADE: "V21",
}


@dataclass(frozen=True, slots=True)
class Violacao:
    regra: Regra
    detalhe: str
    trecho: str = ""
    sugestao: str = ""

    @property
    def codigo(self) -> str:
        return CODIGOS.get(self.regra, "")


@dataclass(frozen=True, slots=True)
class Resultado:
    violacoes: tuple[Violacao, ...]

    @property
    def aprovado(self) -> bool:
        return not self.violacoes

    @property
    def regras(self) -> tuple[Regra, ...]:
        return tuple(dict.fromkeys(v.regra for v in self.violacoes))


class CurriculoInvalido(ValueError):
    def __init__(self, resultado: Resultado) -> None:
        self.resultado = resultado
        resumo = "; ".join(f"{v.regra}: {v.detalhe}" for v in resultado.violacoes)
        super().__init__(resumo)
