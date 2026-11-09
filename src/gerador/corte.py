from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace

from src.conteudo.modelo import Blocos
from src.gerador.configuracao import ConfiguracaoGerador, SlotEntradas
from src.gerador.slots import redacao_para_slot
from src.validador.configuracao import ConfiguracaoValidador

INICIO_DO_CORPO = re.compile(r"\\begin\s*\{document\}")
GEOMETRIA = re.compile(r"(\\usepackage\s*\[)([^\]]*)(\]\s*\{geometry\})")


@dataclass(frozen=True, slots=True)
class Ajustes:
    espaco_reduzido: bool = False
    entrelinha: float | None = None
    margem_vertical_cm: float | None = None


@dataclass(frozen=True, slots=True)
class Candidato:
    slots: dict
    ajustes: Ajustes = Ajustes()


@dataclass(frozen=True, slots=True)
class ContextoDoCorte:
    idioma: str
    blocos: Blocos
    techs_vaga: frozenset[str]
    config: ConfiguracaoGerador
    validador: ConfiguracaoValidador


def _numero(valor: float) -> str:
    return f"{valor:g}"


def aplicar_ajustes(tex: str, ajustes: Ajustes, config: ConfiguracaoGerador) -> str:
    inicio = INICIO_DO_CORPO.search(tex)
    if inicio is None:
        return tex
    preambulo, corpo = tex[: inicio.start()], tex[inicio.start() :]
    if ajustes.espaco_reduzido:
        espaco = config.corte.espaco_vertical
        corpo = corpo.replace(f"\\vspace{{{espaco.de}}}", f"\\vspace{{{espaco.para}}}")
    if ajustes.margem_vertical_cm is not None:
        margem = _numero(ajustes.margem_vertical_cm)
        preambulo = GEOMETRIA.sub(
            lambda achado: f"{achado[1]}{achado[2]},top={margem}cm,bottom={margem}cm{achado[3]}",
            preambulo,
            count=1,
        )
    if ajustes.entrelinha is not None:
        preambulo += f"\\linespread{{{_numero(ajustes.entrelinha)}}}\n"
    return preambulo + corpo


def _slots_de_entradas(config: ConfiguracaoGerador, tipos: list[str] | None = None) -> list[str]:
    return [
        nome
        for nome, declaracao in config.slots.items()
        if isinstance(declaracao, SlotEntradas)
        and (tipos is None or declaracao.tipo_bloco in tipos)
    ]


def remover_quarto_projeto(candidato: Candidato, contexto: ContextoDoCorte) -> Candidato | None:
    minimos = contexto.config.ia.entradas_min
    slots = deepcopy(candidato.slots)
    mudou = False
    for nome in _slots_de_entradas(contexto.config, list(minimos)):
        tipo = contexto.config.slots[nome].tipo_bloco
        if len(slots[nome]) > minimos[tipo]:
            slots[nome] = slots[nome][: minimos[tipo]]
            mudou = True
    return replace(candidato, slots=slots) if mudou else None


def _redacoes_do_bloco(bloco_id: str, contexto: ContextoDoCorte) -> list[dict]:
    bloco = next((b for b in contexto.blocos.blocos if b.id == bloco_id), None)
    if bloco is None:
        return []
    return [redacao_para_slot(bullet.redacao[contexto.idioma]) for bullet in bloco.bullets]


def _mais_curta(bullet: dict, usados: list[dict], opcoes: list[dict]) -> dict | None:
    citadas = {tech.casefold() for tech in bullet["techs"]}
    validas = [
        opcao
        for opcao in opcoes
        if len(opcao["texto"]) < len(bullet["texto"])
        and citadas <= {tech.casefold() for tech in opcao["techs"]}
        and opcao not in usados
    ]
    return min(validas, key=lambda opcao: len(opcao["texto"]), default=None)


def encurtar_bullets(candidato: Candidato, contexto: ContextoDoCorte) -> Candidato | None:
    limite = contexto.config.corte.bullet_longo_chars
    slots = deepcopy(candidato.slots)
    mudou = False
    for nome in _slots_de_entradas(contexto.config):
        for entrada in slots[nome]:
            opcoes = _redacoes_do_bloco(entrada["bloco"], contexto)
            for indice, bullet in enumerate(entrada["bullets"]):
                if len(bullet["texto"]) <= limite:
                    continue
                curta = _mais_curta(bullet, entrada["bullets"], opcoes)
                if curta is not None:
                    entrada["bullets"][indice] = curta
                    mudou = True
    return replace(candidato, slots=slots) if mudou else None


def reduzir_espaco_vertical(candidato: Candidato, contexto: ContextoDoCorte) -> Candidato | None:
    if candidato.ajustes.espaco_reduzido:
        return None
    return replace(candidato, ajustes=replace(candidato.ajustes, espaco_reduzido=True))


def _pontos(bullet: dict, contexto: ContextoDoCorte) -> int:
    citadas = {tech.casefold() for tech in bullet["techs"]}
    return contexto.config.sem_ia.peso_tech * len(
        citadas & {tech.casefold() for tech in contexto.techs_vaga}
    )


def remover_bullet_menos_aderente(
    candidato: Candidato, contexto: ContextoDoCorte
) -> Candidato | None:
    piso = max(1, contexto.config.ia.bullets_min)
    slots = deepcopy(candidato.slots)
    elegiveis = [
        (sum(_pontos(b, contexto) for b in entrada["bullets"]), -ordem, nome, ordem)
        for nome in _slots_de_entradas(
            contexto.config, contexto.config.ia.tipos_na_ordem_dos_blocos
        )
        for ordem, entrada in enumerate(slots[nome])
        if len(entrada["bullets"]) > piso
    ]
    if not elegiveis:
        return None
    _, _, nome, ordem = min(elegiveis)
    bullets = slots[nome][ordem]["bullets"]
    pior = min(range(len(bullets)), key=lambda i: (_pontos(bullets[i], contexto), -i))
    del bullets[pior]
    return replace(candidato, slots=slots)


def reduzir_entrelinha(candidato: Candidato, contexto: ContextoDoCorte) -> Candidato | None:
    minimo = contexto.validador.layout.por_idioma[contexto.idioma].linespread_min
    if candidato.ajustes.entrelinha is not None and candidato.ajustes.entrelinha <= minimo:
        return None
    return replace(candidato, ajustes=replace(candidato.ajustes, entrelinha=minimo))


def reduzir_margem_vertical(candidato: Candidato, contexto: ContextoDoCorte) -> Candidato | None:
    piso_cm = contexto.validador.layout.por_idioma[contexto.idioma].margem_min_mm / 10
    margem = max(contexto.config.corte.margem_vertical_cm, piso_cm)
    if candidato.ajustes.margem_vertical_cm == margem:
        return None
    return replace(candidato, ajustes=replace(candidato.ajustes, margem_vertical_cm=margem))


PASSOS: dict[str, Callable[[Candidato, ContextoDoCorte], Candidato | None]] = {
    "remover_quarto_projeto": remover_quarto_projeto,
    "encurtar_bullets": encurtar_bullets,
    "reduzir_espaco_vertical": reduzir_espaco_vertical,
    "remover_bullet_menos_aderente": remover_bullet_menos_aderente,
    "reduzir_entrelinha": reduzir_entrelinha,
    "reduzir_margem_vertical": reduzir_margem_vertical,
}
