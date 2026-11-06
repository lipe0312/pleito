from __future__ import annotations

import re
from dataclasses import dataclass

from src.conteudo.modelo import Estrito
from src.gerador.slots import TextoComTechs
from src.padroes.configuracao import ConfiguracaoPadroes, Faixa

TOLERANCIA_DO_TOTAL = 6


class CurriculoAvaliado(Estrito):
    sobre: TextoComTechs
    bullets_por_entrada: list[list[TextoComTechs]]


@dataclass(frozen=True, slots=True)
class Nota:
    total: float
    notas: dict[str, float]
    aprovado: bool


def _contem(texto: str, termo: str) -> bool:
    padrao = rf"(?<!\w){re.escape(termo)}(?!\w)"
    return re.search(padrao, texto, flags=re.IGNORECASE) is not None


def _abre_com(texto: str, prefixo: str) -> bool:
    return texto.strip().casefold().startswith(prefixo.casefold())


def _dentro(valor: int, faixa: Faixa) -> bool:
    return faixa.minimo <= valor <= faixa.maximo


def _abertura(texto: str) -> str:
    palavras = re.findall(r"\w+", texto.casefold())
    return palavras[0] if palavras else ""


def _bullet_vago(
    bullet: TextoComTechs, config: ConfiguracaoPadroes, idioma: str
) -> bool:
    inflados = (
        config.senioridade_inflada.verbos[idioma] + config.senioridade_inflada.expressoes[idioma]
    )
    return (
        not _dentro(len(set(map(str.casefold, bullet.techs))), config.bullet.techs)
        or not _dentro(len(bullet.texto.strip()), config.bullet.chars)
        or any(_abre_com(bullet.texto, abertura) for abertura in config.aberturas_vagas[idioma])
        or any(_contem(bullet.texto, termo) for termo in config.termos_vagos[idioma])
        or any(_contem(bullet.texto, termo) for termo in inflados)
    )


def _cobertura(curriculo: CurriculoAvaliado, techs_pedidas: list[str]) -> float:
    pedidas = {tech.casefold() for tech in techs_pedidas}
    if not pedidas:
        return 1.0
    citadas = {tech.casefold() for tech in curriculo.sobre.techs}
    for bullets in curriculo.bullets_por_entrada:
        citadas |= {tech.casefold() for bullet in bullets for tech in bullet.techs}
    return len(pedidas & citadas) / len(pedidas)


def _aderencia(
    curriculo: CurriculoAvaliado, config: ConfiguracaoPadroes, idioma: str, familia: str
) -> float:
    termos = config.foco_sobre[familia][idioma]
    achados = sum(1 for termo in termos if _contem(curriculo.sobre.texto, termo))
    alvo = min(len(termos), config.rubrica.aderencia_termos_alvo)
    return min(1.0, achados / alvo)


def _verbo_repetido(curriculo: CurriculoAvaliado) -> float:
    total = sum(len(bullets) for bullets in curriculo.bullets_por_entrada)
    if total == 0:
        return 0.0
    repetidos = 0
    for bullets in curriculo.bullets_por_entrada:
        aberturas = [_abertura(bullet.texto) for bullet in bullets]
        repetidos += len(aberturas) - len(set(aberturas))
    return 1 - repetidos / total


def _bullet_vago_nota(
    curriculo: CurriculoAvaliado, config: ConfiguracaoPadroes, idioma: str
) -> float:
    bullets = [bullet for entrada in curriculo.bullets_por_entrada for bullet in entrada]
    if not bullets:
        return 0.0
    vagos = sum(1 for bullet in bullets if _bullet_vago(bullet, config, idioma))
    return 1 - vagos / len(bullets)


def _sobre_generico(
    curriculo: CurriculoAvaliado, config: ConfiguracaoPadroes, idioma: str
) -> float:
    sobre = curriculo.sobre
    verificacoes = [
        not any(_contem(sobre.texto, frase) for frase in config.sobre.frases_vazias[idioma]),
        len(set(map(str.casefold, sobre.techs))) >= config.sobre.techs_minimo,
        _dentro(len(sobre.texto.strip()), config.sobre.chars),
    ]
    return sum(verificacoes) / len(verificacoes)


def avaliar(
    config: ConfiguracaoPadroes,
    curriculo: CurriculoAvaliado,
    idioma: str,
    familia: str,
    techs_pedidas: list[str],
) -> Nota:
    if idioma not in config.idiomas:
        raise KeyError(idioma)
    config.foco_sobre[familia]
    notas = {
        "cobertura_techs": _cobertura(curriculo, techs_pedidas),
        "aderencia_familia": _aderencia(curriculo, config, idioma, familia),
        "verbo_repetido": _verbo_repetido(curriculo),
        "bullet_vago": _bullet_vago_nota(curriculo, config, idioma),
        "sobre_generico": _sobre_generico(curriculo, config, idioma),
    }
    total = sum(config.rubrica.criterios[nome].peso * valor for nome, valor in notas.items())
    total = round(total, TOLERANCIA_DO_TOTAL)
    return Nota(total=total, notas=notas, aprovado=total >= config.rubrica.nota_minima)
