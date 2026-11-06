from __future__ import annotations

import re

from src.conteudo.modelo import Bloco, Blocos, Bullet, Inventario
from src.gerador.configuracao import (
    ConfiguracaoGerador,
    SlotEntradas,
    SlotListaTexto,
    SlotTexto,
)
from src.gerador.erros import IdiomaNaoSuportado, SlotAusente
from src.gerador.resposta import Enfase, disciplinas_do_inventario, techs_do_bloco
from src.gerador.slots import redacao_para_slot
from src.padroes.configuracao import ConfiguracaoPadroes


def techs_da_vaga(vaga: str, inventario: Inventario) -> frozenset[str]:
    return frozenset(
        item.tech
        for item in inventario.techs
        if re.search(rf"(?<!\w){re.escape(item.tech)}(?!\w)", vaga, re.IGNORECASE)
    )


class _Criterio:
    def __init__(
        self, familia: str, techs_vaga: frozenset[str], config: ConfiguracaoGerador, idioma: str
    ) -> None:
        self.familia = familia
        self.techs_vaga = techs_vaga
        self.config = config
        self.idioma = idioma

    def techs_do_bullet(self, bullet: Bullet) -> list[str]:
        return redacao_para_slot(bullet.redacao[self.idioma])["techs"]

    def pontos(self, bullet: Bullet) -> int:
        pesos = self.config.sem_ia
        return pesos.peso_familia * (self.familia in bullet.familias) + pesos.peso_tech * len(
            self.techs_vaga & set(self.techs_do_bullet(bullet))
        )

    def melhores_bullets(self, bloco: Bloco, limite: int) -> list[Bullet]:
        ordem = sorted(range(len(bloco.bullets)), key=lambda i: (-self.pontos(bloco.bullets[i]), i))
        return [bloco.bullets[i] for i in ordem[:limite]]


def _entrada(bloco: Bloco, bullets: list[Bullet], criterio: _Criterio) -> dict:
    return {
        "bloco": bloco.id,
        "bullets": [redacao_para_slot(bullet.redacao[criterio.idioma]) for bullet in bullets],
    }


def _entradas(
    declaracao: SlotEntradas, blocos: Blocos, criterio: _Criterio
) -> tuple[list[dict], Enfase]:
    config = criterio.config
    do_tipo = [bloco for bloco in blocos.blocos if bloco.tipo == declaracao.tipo_bloco]
    limite_bullets = config.sem_ia.bullets_por_tipo[declaracao.tipo_bloco]
    escolhidos = {bloco.id: criterio.melhores_bullets(bloco, limite_bullets) for bloco in do_tipo}
    if declaracao.tipo_bloco in config.ia.tipos_na_ordem_dos_blocos:
        ordenados = do_tipo
    else:
        pontos = {
            bloco.id: sum(criterio.pontos(bullet) for bullet in escolhidos[bloco.id])
            for bloco in do_tipo
        }
        ordem = sorted(range(len(do_tipo)), key=lambda i: (-pontos[do_tipo[i].id], i))
        total = config.sem_ia.entradas_por_tipo.get(declaracao.tipo_bloco, len(do_tipo))
        ordenados = [do_tipo[i] for i in ordem[:total]]
    enfase: Enfase = {}
    if declaracao.tipo_bloco in config.ia.tipos_com_enfase:
        for bloco in ordenados:
            destaque = [
                tech
                for bullet in escolhidos[bloco.id]
                for tech in criterio.techs_do_bullet(bullet)
                if tech in criterio.techs_vaga and tech in techs_do_bloco(bloco)
            ]
            enfase[bloco.id] = tuple(dict.fromkeys(destaque))[: config.ia.enfase_max]
    return [_entrada(bloco, escolhidos[bloco.id], criterio) for bloco in ordenados], enfase


def _disciplinas(
    declaracao: SlotListaTexto, inventario: Inventario, techs_vaga: frozenset[str]
) -> list[str]:
    puxadas = [
        ancora.ref
        for item in inventario.techs
        if item.tech in techs_vaga
        for ancora in item.ancoras
        if ancora.tipo == "disciplina"
    ]
    todas = list(dict.fromkeys([*puxadas, *disciplinas_do_inventario(inventario)]))
    return [nome for nome in todas if len(nome) <= declaracao.max_chars][: declaracao.max_itens]


def slots_sem_ia(
    familia: str,
    idioma: str,
    vaga: str,
    blocos: Blocos,
    inventario: Inventario,
    config: ConfiguracaoGerador,
    padroes: ConfiguracaoPadroes,
) -> tuple[dict, Enfase]:
    padroes.exigir(idioma, familia)
    if idioma not in blocos.idiomas:
        raise IdiomaNaoSuportado(f"sem blocos para {idioma!r}")
    techs_vaga = techs_da_vaga(vaga, inventario)
    criterio = _Criterio(familia, techs_vaga, config, idioma)
    slots: dict = {}
    enfase: Enfase = {}
    for nome, declaracao in config.slots.items():
        if isinstance(declaracao, SlotTexto):
            fonte = next((b for b in blocos.blocos if b.tipo == nome and b.redacao), None)
            if fonte is None:
                raise SlotAusente(f"sem bloco de {nome} com redacao")
            slots[nome] = redacao_para_slot(fonte.redacao[idioma])
        elif isinstance(declaracao, SlotListaTexto):
            slots[nome] = _disciplinas(declaracao, inventario, techs_vaga)
        else:
            slots[nome], parcial = _entradas(declaracao, blocos, criterio)
            enfase |= parcial
    return slots, enfase
