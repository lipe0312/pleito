from __future__ import annotations

import json
from collections.abc import Callable

from src.avaliacao.conjunto import Conteudo
from src.gerador.configuracao import ConfiguracaoGerador, SlotEntradas, SlotListaTexto, SlotTexto
from src.gerador.resposta import techs_do_bloco
from src.gerador.slots import redacao_para_slot
from src.llm.roteador import RespostaTransporte

Transporte = Callable[[dict[str, object]], RespostaTransporte]


def resposta_de_referencia(conteudo: Conteudo, idioma: str, config: ConfiguracaoGerador) -> dict:
    blocos = conteudo.blocos.blocos
    permitidas = {item.tech for item in conteudo.inventario.techs}
    resposta: dict = {}
    for nome, declaracao in config.slots.items():
        if isinstance(declaracao, SlotTexto):
            bloco = next(b for b in blocos if b.tipo == declaracao.tipo_bloco)
            resposta[nome] = redacao_para_slot(bloco.redacao[idioma])
        elif isinstance(declaracao, SlotListaTexto):
            resposta[nome] = []
        elif isinstance(declaracao, SlotEntradas):
            do_tipo = [b for b in blocos if b.tipo == declaracao.tipo_bloco]
            entradas = []
            for bloco in do_tipo[: declaracao.max_entradas]:
                entrada: dict = {}
                if declaracao.tipo_bloco in config.ia.tipos_com_enfase:
                    entrada["enfase"] = sorted(techs_do_bloco(bloco) & permitidas)[
                        : config.ia.enfase_max
                    ]
                entrada["bloco"] = bloco.id
                entrada["bullets"] = [
                    {"id": bullet.id, **redacao_para_slot(bullet.redacao[idioma])}
                    for bullet in bloco.bullets[: declaracao.max_bullets]
                ]
                entradas.append(entrada)
            resposta[nome] = entradas
    return resposta


def transporte_fixo(resposta: dict, tokens_entrada: int, tokens_saida: int) -> Transporte:
    texto = json.dumps(resposta, ensure_ascii=False)

    def transporte(pedido: dict[str, object]) -> RespostaTransporte:
        return RespostaTransporte(texto, tokens_entrada, tokens_saida)

    return transporte
