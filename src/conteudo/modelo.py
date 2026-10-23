from __future__ import annotations

from collections import Counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identificador = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$")]
TextoNaoVazio = Annotated[str, StringConstraints(min_length=1)]
TipoBloco = Literal["sobre", "experiencia", "projeto"]
TipoAncora = Literal["experiencia", "projeto", "disciplina"]


class TecnologiaSemAncora(ValueError):
    pass


class AncoraInvalida(ValueError):
    pass


class Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Bullet(Estrito):
    id: Identificador
    redacao: dict[str, TextoNaoVazio] = Field(min_length=1)
    techs: list[TextoNaoVazio] = []
    familias: list[Identificador] = []


class Bloco(Estrito):
    id: Identificador
    tipo: TipoBloco
    imutavel: dict[str, dict[str, str]] = {}
    redacao: dict[str, TextoNaoVazio] = {}
    techs: list[TextoNaoVazio] = []
    bullets: list[Bullet] = []


class Blocos(Estrito):
    idiomas: list[Identificador] = Field(min_length=1)
    blocos: list[Bloco]

    @model_validator(mode="after")
    def _ids_unicos_e_idiomas_completos(self) -> Blocos:
        ids = [bloco.id for bloco in self.blocos]
        ids += [bullet.id for bloco in self.blocos for bullet in bloco.bullets]
        repetidos = sorted(nome for nome, total in Counter(ids).items() if total > 1)
        if repetidos:
            raise ValueError(f"id duplicado: {repetidos}")
        esperado = set(self.idiomas)
        for bloco in self.blocos:
            textos = [bloco.redacao] if bloco.redacao else []
            textos += list(bloco.imutavel.values())
            textos += [bullet.redacao for bullet in bloco.bullets]
            if any(set(texto) != esperado for texto in textos):
                raise ValueError(f"bloco {bloco.id} sem todos os idiomas {sorted(esperado)}")
        return self


class Ancora(Estrito):
    tipo: TipoAncora
    ref: TextoNaoVazio
    fonte: TextoNaoVazio


class ItemInventario(Estrito):
    tech: TextoNaoVazio
    ancoras: list[Ancora] = Field(min_length=1)


class Equivalencia(Estrito):
    pedido: TextoNaoVazio
    tem: TextoNaoVazio
    citar: TextoNaoVazio


class Inventario(Estrito):
    techs: list[ItemInventario]
    equivalencias: list[Equivalencia] = []

    @model_validator(mode="after")
    def _techs_unicas(self) -> Inventario:
        repetidas = sorted(
            nome for nome, total in Counter(item.tech for item in self.techs).items() if total > 1
        )
        if repetidas:
            raise ValueError(f"tech duplicada no inventario: {repetidas}")
        return self


def validar_conteudo(blocos: Blocos, inventario: Inventario) -> None:
    tipos_por_id = {bloco.id: bloco.tipo for bloco in blocos.blocos}
    for item in inventario.techs:
        for ancora in item.ancoras:
            if ancora.tipo == "disciplina":
                continue
            if tipos_por_id.get(ancora.ref) != ancora.tipo:
                raise AncoraInvalida(f"{item.tech}: ancora {ancora.tipo} {ancora.ref} inexistente")
    ancoradas = {item.tech for item in inventario.techs}
    citadas = [tech for bloco in blocos.blocos for tech in bloco.techs]
    citadas += [tech for bloco in blocos.blocos for b in bloco.bullets for tech in b.techs]
    soltas = sorted(set(citadas) - ancoradas)
    if soltas:
        raise TecnologiaSemAncora(f"tecnologia sem ancora no inventario: {soltas}")
