from __future__ import annotations

from src.conteudo.modelo import Bloco, Blocos, Estrito, Inventario
from src.gerador.configuracao import (
    ConfiguracaoGerador,
    SlotEntradas,
    SlotListaTexto,
    SlotTexto,
)
from src.gerador.erros import SlotInvalido

Enfase = dict[str, tuple[str, ...]]


def disciplinas_do_inventario(inventario: Inventario) -> list[str]:
    return list(
        dict.fromkeys(
            ancora.ref
            for item in inventario.techs
            for ancora in item.ancoras
            if ancora.tipo == "disciplina"
        )
    )


def techs_do_bloco(bloco: Bloco) -> frozenset[str]:
    return frozenset(bloco.techs) | {tech for bullet in bloco.bullets for tech in bullet.techs}


def _lista_de_disciplinas(valor: list[str], inventario: Inventario, nome: str) -> list[str]:
    conhecidas = set(disciplinas_do_inventario(inventario))
    desconhecidas = sorted(set(valor) - conhecidas)
    if desconhecidas:
        raise SlotInvalido(f"{nome}: item fora do inventario: {desconhecidas}")
    if len(set(valor)) != len(valor):
        raise SlotInvalido(f"{nome}: item repetido")
    return valor


def _entradas(
    nome: str,
    valor: list[dict],
    declaracao: SlotEntradas,
    blocos: Blocos,
    inventario: Inventario,
    config: ConfiguracaoGerador,
) -> tuple[list[dict], Enfase]:
    do_tipo = [bloco for bloco in blocos.blocos if bloco.tipo == declaracao.tipo_bloco]
    por_id = {bloco.id: bloco for bloco in do_tipo}
    ids = [entrada["bloco"] for entrada in valor]
    inexistentes = sorted(set(ids) - set(por_id))
    if inexistentes:
        raise SlotInvalido(f"{nome}: bloco inexistente ou de outro tipo: {inexistentes}")
    if len(set(ids)) != len(ids):
        raise SlotInvalido(f"{nome}: bloco repetido")
    if declaracao.tipo_bloco in config.ia.tipos_na_ordem_dos_blocos and ids != [
        bloco.id for bloco in do_tipo
    ]:
        raise SlotInvalido(f"{nome}: precisa trazer todos os blocos na ordem dos blocos")
    permitidas = {item.tech for item in inventario.techs}
    saida = []
    enfase: Enfase = {}
    for entrada in valor:
        bloco = por_id[entrada["bloco"]]
        ids_dos_bullets = [bullet["id"] for bullet in entrada["bullets"]]
        alheios = sorted(set(ids_dos_bullets) - {bullet.id for bullet in bloco.bullets})
        if alheios:
            raise SlotInvalido(f"{nome}: bullet inexistente no bloco {bloco.id}: {alheios}")
        if len(set(ids_dos_bullets)) != len(ids_dos_bullets):
            raise SlotInvalido(f"{nome}: bullet repetido no bloco {bloco.id}")
        if "enfase" in entrada:
            fora = sorted(set(entrada["enfase"]) - (techs_do_bloco(bloco) & permitidas))
            if fora:
                raise SlotInvalido(f"{nome}: enfase fora das techs do bloco {bloco.id}: {fora}")
            enfase[bloco.id] = tuple(dict.fromkeys(entrada["enfase"]))
        saida.append(
            {
                "bloco": bloco.id,
                "bullets": [
                    {"texto": bullet["texto"], "techs": bullet["techs"]}
                    for bullet in entrada["bullets"]
                ],
            }
        )
    return saida, enfase


def slots_da_resposta(
    resposta: Estrito, blocos: Blocos, inventario: Inventario, config: ConfiguracaoGerador
) -> tuple[dict, Enfase]:
    dados = resposta.model_dump()
    slots: dict = {}
    enfase: Enfase = {}
    for nome, declaracao in config.slots.items():
        if isinstance(declaracao, SlotTexto):
            slots[nome] = dados[nome]
        elif isinstance(declaracao, SlotListaTexto):
            slots[nome] = _lista_de_disciplinas(dados[nome], inventario, nome)
        else:
            slots[nome], parcial = _entradas(
                nome, dados[nome], declaracao, blocos, inventario, config
            )
            enfase |= parcial
    return slots, enfase
