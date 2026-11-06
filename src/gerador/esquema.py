from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints, create_model

from src.conteudo.modelo import Estrito, Identificador
from src.gerador.configuracao import (
    ConfiguracaoGerador,
    SlotListaTexto,
    SlotTexto,
)


def _texto(max_chars: int) -> type:
    return Annotated[str, StringConstraints(min_length=1, max_length=max_chars)]


def esquema_dos_slots(config: ConfiguracaoGerador) -> type[Estrito]:
    ia = config.ia
    techs = Annotated[list[_texto(ia.tech_max_chars)], Field(max_length=ia.techs_max)]
    campos: dict[str, tuple] = {}
    for nome, declaracao in config.slots.items():
        if isinstance(declaracao, SlotTexto):
            modelo = create_model(
                f"Texto_{nome}",
                __base__=Estrito,
                texto=(_texto(declaracao.max_chars), ...),
                techs=(techs, ...),
            )
            campos[nome] = (modelo, ...)
        elif isinstance(declaracao, SlotListaTexto):
            itens = list[_texto(declaracao.max_chars)]
            campos[nome] = (Annotated[itens, Field(max_length=declaracao.max_itens)], ...)
        else:
            bullet = create_model(
                f"Bullet_{nome}",
                __base__=Estrito,
                id=(Identificador, ...),
                texto=(_texto(declaracao.max_chars), ...),
                techs=(techs, ...),
            )
            extras: dict[str, tuple] = {}
            if declaracao.tipo_bloco in ia.tipos_com_enfase:
                extras["enfase"] = (
                    Annotated[list[_texto(ia.tech_max_chars)], Field(max_length=ia.enfase_max)],
                    ...,
                )
            entrada = create_model(
                f"Entrada_{nome}",
                __base__=Estrito,
                bloco=(Identificador, ...),
                **extras,
                bullets=(
                    Annotated[
                        list[bullet],
                        Field(min_length=ia.bullets_min, max_length=declaracao.max_bullets),
                    ],
                    ...,
                ),
            )
            campos[nome] = (
                Annotated[
                    list[entrada],
                    Field(
                        min_length=ia.entradas_min.get(declaracao.tipo_bloco, 0),
                        max_length=declaracao.max_entradas,
                    ),
                ],
                ...,
            )
    return create_model("SlotsDoCurriculo", __base__=Estrito, **campos)
