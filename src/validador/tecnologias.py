from __future__ import annotations

import re

from src.conteudo.decompor import ESCAPE, TECH
from src.conteudo.modelo import Inventario
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.latex import corpo_do_tex
from src.validador.resultado import Regra, Violacao

MARCADOR = re.compile(r"\\tech(?![A-Za-z])")
DESTINO_DO_LINK = re.compile(r"\\href\s*\{[^{}]*\}")
COMANDO_COM_LETRAS = re.compile(r"\\[A-Za-z]+")
SIMBOLO_DE_CONTROLE = re.compile(r"\\[^A-Za-z]", re.S)
ESPACOS = re.compile(r"\s+")


def _violacao(detalhe: str) -> Violacao:
    return Violacao(Regra.TECNOLOGIA, detalhe)


def _palavra(nome: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(nome)}(?!\w)", re.IGNORECASE)


def _nomes_do_inventario(inventario: Inventario) -> list[str]:
    return sorted({item.tech for item in inventario.techs}, key=len, reverse=True)


def validar_tecnologias_no_texto(
    texto: str, inventario: Inventario, config: ConfiguracaoValidador
) -> list[Violacao]:
    restante = ESPACOS.sub(" ", texto)
    for nome in _nomes_do_inventario(inventario):
        restante = _palavra(nome).sub(" ", restante)
    conhecidas = list(config.tecnologias_conhecidas)
    conhecidas += [equivalencia.pedido for equivalencia in inventario.equivalencias]
    proibidas = {nome.casefold(): nome for nome in conhecidas}
    achadas = [nome for nome in proibidas.values() if _palavra(nome).search(restante)]
    return [_violacao(f"tecnologia fora do inventario: {nome}") for nome in sorted(achadas)]


def _texto_visivel(corpo: str) -> str:
    sem_link = DESTINO_DO_LINK.sub(" ", TECH.sub(" ", corpo))
    desescapado = ESCAPE.sub(r"\1", sem_link)
    sem_simbolos = SIMBOLO_DE_CONTROLE.sub(" ", desescapado)
    return COMANDO_COM_LETRAS.sub("", sem_simbolos).replace("{", "").replace("}", "")


def validar_tecnologias(
    tex: str, inventario: Inventario, config: ConfiguracaoValidador
) -> list[Violacao]:
    corpo = corpo_do_tex(tex, config)
    permitidas = {item.tech.casefold() for item in inventario.techs}
    marcadas = [ESCAPE.sub(r"\1", nome).strip() for nome in TECH.findall(corpo)]
    violacoes = []
    if len(MARCADOR.findall(corpo)) != len(marcadas):
        violacoes.append(_violacao("marcador tech malformado"))
    violacoes += [
        _violacao(f"tecnologia fora do inventario: {nome}")
        for nome in dict.fromkeys(marcadas)
        if nome.casefold() not in permitidas
    ]
    violacoes += validar_tecnologias_no_texto(_texto_visivel(corpo), inventario, config)
    return violacoes
