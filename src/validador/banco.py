from __future__ import annotations

import unicodedata

from pydantic import Field

from src.conteudo.modelo import Estrito, Identificador, Inventario, TextoNaoVazio
from src.conteudo.sugestoes import Sugestoes
from src.validador.configuracao import ConfiguracaoValidador

ORIGEM_DO_INVENTARIO = "inventario"
ORIGEM_SEM_MARCA = "sugestao"
SEPARADOR_DA_MARCA = ":"


class Evidencia(Estrito):
    origem: Identificador
    ref: TextoNaoVazio
    fonte: TextoNaoVazio


class TecnologiaDoBanco(Estrito):
    tech: TextoNaoVazio
    evidencias: list[Evidencia] = Field(min_length=1)


class BancoTecnologias(Estrito):
    tecnologias: list[TecnologiaDoBanco]

    def evidencias_de(self, nome: str) -> list[Evidencia]:
        chave = chave_da_tecnologia(nome)
        achadas: list[Evidencia] = []
        for item in self.tecnologias:
            if chave_da_tecnologia(item.tech) == chave:
                achadas += item.evidencias
        return achadas


def chave_da_tecnologia(nome: str) -> str:
    return unicodedata.normalize("NFKC", nome).casefold()


def forca_da_evidencia(evidencia: Evidencia, config: ConfiguracaoValidador) -> str:
    return config.tecnologias.forca_por_origem.get(
        evidencia.origem, config.tecnologias.forca_padrao
    )


def _origem_da_marca(marca: str) -> str:
    origem = marca.split(SEPARADOR_DA_MARCA, 1)[0].strip().casefold()
    if origem and origem.replace("_", "").isalnum() and origem.isascii():
        return origem
    return ORIGEM_SEM_MARCA


def montar_banco(inventario: Inventario, sugestoes: Sugestoes | None) -> BancoTecnologias:
    por_chave: dict[str, tuple[str, list[Evidencia]]] = {}

    def somar(tech: str, evidencia: Evidencia) -> None:
        _, lista = por_chave.setdefault(chave_da_tecnologia(tech), (tech, []))
        if evidencia not in lista:
            lista.append(evidencia)

    for item in inventario.techs:
        for ancora in item.ancoras:
            somar(
                item.tech,
                Evidencia(
                    origem=ORIGEM_DO_INVENTARIO,
                    ref=f"{ancora.tipo}{SEPARADOR_DA_MARCA}{ancora.ref}",
                    fonte=ancora.fonte,
                ),
            )
    for sugestao in sugestoes.sugestoes if sugestoes else []:
        if sugestao.tipo != "tecnologia_nova" or sugestao.status == "rejeitada":
            continue
        if sugestao.tech is None or sugestao.ancora is None:
            continue
        for marca in sugestao.evidencias:
            somar(
                sugestao.tech,
                Evidencia(
                    origem=_origem_da_marca(marca),
                    ref=sugestao.projeto.id,
                    fonte=sugestao.ancora.fonte,
                ),
            )
    return BancoTecnologias(
        tecnologias=[
            TecnologiaDoBanco(tech=nome, evidencias=lista) for nome, lista in por_chave.values()
        ]
    )
