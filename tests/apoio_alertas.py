from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.email.modelo import Email
from tests.test_email_organizador import mensagem

MARCADOR = "--CARTOES--"
PASTA = Path(__file__).parent / "fixtures"


@dataclass(frozen=True, slots=True)
class CasoAlerta:
    nome: str
    remetente: str
    assunto: str
    autenticacao: str
    corpo: str
    esperado: dict = field(default_factory=dict)

    @property
    def email(self) -> Email:
        return Email(
            remetente=self.remetente,
            assunto=self.assunto,
            corpo=self.corpo,
            autenticacao=self.autenticacao,
        )

    def mensagem(self, identificador: str) -> dict:
        return mensagem(
            identificador, self.remetente, self.assunto, self.corpo, self.autenticacao
        )


def casos(plataforma: str = "linkedin") -> list[CasoAlerta]:
    bruto = yaml.safe_load((PASTA / f"alertas_{plataforma}.yaml").read_text(encoding="utf-8"))
    lista = []
    for caso in bruto["casos"]:
        cartoes = "".join(bruto[nome] for nome in caso["cartoes"])
        lista.append(
            CasoAlerta(
                nome=caso["nome"],
                remetente=caso["remetente"],
                assunto=caso["assunto"],
                autenticacao=caso["autenticacao"],
                corpo=caso["corpo"].replace(MARCADOR, cartoes),
                esperado=caso["esperado"],
            )
        )
    return lista


def caso(nome: str, plataforma: str = "linkedin") -> CasoAlerta:
    return next(c for c in casos(plataforma) if c.nome == nome)


class DestinoFalso:
    def __init__(self, falhar: bool = False) -> None:
        self.lotes: list[list] = []
        self.falhar = falhar

    def gravar(self, vagas: list):
        if self.falhar:
            raise RuntimeError("banco indisponivel")
        self.lotes.append(list(vagas))

    @property
    def vagas(self) -> list:
        return [vaga for lote in self.lotes for vaga in lote]
