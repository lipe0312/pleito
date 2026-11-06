from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Regra(StrEnum):
    PAGINAS = "paginas"
    TECNOLOGIA = "tecnologia"
    TRAVESSAO = "travessao"
    LATEX = "latex"
    CARACTERE_INVISIVEL = "caractere_invisivel"


@dataclass(frozen=True, slots=True)
class Violacao:
    regra: Regra
    detalhe: str


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
