from __future__ import annotations

from dataclasses import dataclass

from src.config import carregar


@dataclass(frozen=True, slots=True)
class Rotina:
    nome: str
    comando: tuple[str, ...]
    horario: str | None = None
    intervalo_min: int | None = None

    @property
    def hora_e_minuto(self) -> tuple[int, int]:
        hora, minuto = self.horario.split(":")
        return int(hora), int(minuto)


@dataclass(frozen=True, slots=True)
class Agendamento:
    rotulo: str
    tolerancia_min: int
    retry_ao_acordar: bool
    rotinas: tuple[Rotina, ...]


def agendamento_do_config() -> Agendamento:
    limites = carregar("limites")
    horarios = limites["horarios"]
    bloco = limites["agendamento"]
    rotinas = []
    for nome, definicao in bloco["rotinas"].items():
        horario = horarios[definicao["horario"]] if "horario" in definicao else None
        intervalo = horarios[definicao["intervalo"]] if "intervalo" in definicao else None
        rotinas.append(Rotina(nome, tuple(definicao["comando"]), horario, intervalo))
    return Agendamento(
        rotulo=bloco["rotulo"],
        tolerancia_min=int(bloco["tolerancia_min"]),
        retry_ao_acordar=bool(horarios["retry_ao_acordar"]),
        rotinas=tuple(rotinas),
    )
