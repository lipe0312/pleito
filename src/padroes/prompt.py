from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from src.config import RAIZ
from src.conteudo.modelo import Blocos, Inventario
from src.gerador.slots import redacao_para_slot
from src.padroes.configuracao import PASTA_DOS_PROMPTS, ConfiguracaoPadroes

CABECALHO = re.compile(r"\A---\nversao: (?P<versao>[1-9][0-9]*)\n---\n")
MARCADOR = re.compile(r"\{\{(?P<nome>[a-z0-9_]+)\}\}")
SEPARADOR_DE_LISTA = ", "


class ModeloDePromptInvalido(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PromptMontado:
    texto: str
    versao: int
    sha256: str


def _lista(itens: list[str]) -> str:
    return SEPARADOR_DE_LISTA.join(itens)


def _linhas(itens: list[str]) -> str:
    return "\n".join(f"- {item}" for item in itens)


def _neutralizar(vaga: str, config: ConfiguracaoPadroes) -> str:
    marcas = re.compile(
        "|".join(re.escape(marca) for marca in (config.marcacao.abre, config.marcacao.fecha))
    )
    texto = vaga[: config.marcacao.vaga_max_chars]
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = marcas.sub(config.marcacao.neutro, texto)
    return texto[: config.marcacao.vaga_max_chars]


def _sem_marcas(texto: str, config: ConfiguracaoPadroes) -> str:
    return texto.replace(config.marcacao.abre, config.marcacao.neutro).replace(
        config.marcacao.fecha, config.marcacao.neutro
    )


def _blocos_do_idioma(blocos: Blocos, idioma: str, config: ConfiguracaoPadroes) -> str:
    itens = [
        {
            "id": bloco.id,
            "tipo": bloco.tipo,
            "fatos": {campo: textos[idioma] for campo, textos in bloco.imutavel.items()},
            "redacao": redacao_para_slot(bloco.redacao[idioma]) if bloco.redacao else None,
            "techs": bloco.techs,
            "bullets": [
                {"id": bullet.id, "redacao": redacao_para_slot(bullet.redacao[idioma])}
                for bullet in bloco.bullets
            ],
        }
        for bloco in blocos.blocos
    ]
    return _sem_marcas(json.dumps(itens, ensure_ascii=False, indent=1), config)


def _valores(
    config: ConfiguracaoPadroes,
    idioma: str,
    familia: str,
    vaga: str,
    blocos: Blocos,
    inventario: Inventario,
) -> dict[str, str]:
    config.exigir(idioma, familia)
    foco = config.foco_sobre[familia][idioma]
    criterios = config.rubrica.criterios.values()
    return {
        "idioma": idioma,
        "nao_invencao": _linhas(config.nao_invencao),
        "marca_abre": config.marcacao.abre,
        "marca_fecha": config.marcacao.fecha,
        "marca_neutra": config.marcacao.neutro,
        "verbos_aceitos": _lista(config.verbos_abertura_aceitos[idioma]),
        "aberturas_vagas": _lista(config.aberturas_vagas[idioma]),
        "termos_vagos": _lista(config.termos_vagos[idioma]),
        "bullet_formula": config.bullet.formula,
        "bullet_chars_min": str(config.bullet.chars.minimo),
        "bullet_chars_max": str(config.bullet.chars.maximo),
        "bullet_techs_min": str(config.bullet.techs.minimo),
        "bullet_techs_max": str(config.bullet.techs.maximo),
        "senioridade_verbos": _lista(config.senioridade_inflada.verbos[idioma]),
        "senioridade_expressoes": _lista(config.senioridade_inflada.expressoes[idioma]),
        "pontuacao_terminador": config.pontuacao.terminador_bullet,
        "pontuacao_separador": config.pontuacao.separador_interno,
        "pontuacao_proibidos": _lista(config.pontuacao.proibidos),
        "sobre_chars_min": str(config.sobre.chars.minimo),
        "sobre_chars_max": str(config.sobre.chars.maximo),
        "sobre_techs_minimo": str(config.sobre.techs_minimo),
        "foco_sobre": _lista(foco),
        "frases_vazias": _lista(config.sobre.frases_vazias[idioma]),
        "termos_ingles": _lista(config.termos_em_ingles_na_versao_pt),
        "ordem_secoes": _lista(config.ordem_secoes),
        "secoes_proibidas": _lista(config.secoes_proibidas),
        "ordem_de_corte": _lista(config.ordem_de_corte),
        "nunca_no_corte": _lista(config.nunca_no_corte),
        "rubrica_nota_minima": str(config.rubrica.nota_minima),
        "rubrica": _linhas(
            [f"{criterio.descricao} (peso {criterio.peso})" for criterio in criterios]
        ),
        "blocos": _blocos_do_idioma(blocos, idioma, config),
        "inventario": _sem_marcas(_lista([item.tech for item in inventario.techs]), config),
        "vaga": _neutralizar(vaga, config),
    }


def _renderizar(corpo: str, valores: dict[str, str]) -> str:
    usados = {achado.group("nome") for achado in MARCADOR.finditer(corpo)}
    desconhecidos = sorted(usados - set(valores))
    if desconhecidos:
        raise ModeloDePromptInvalido(f"marcador desconhecido no modelo: {desconhecidos}")
    sem_uso = sorted(set(valores) - usados)
    if sem_uso:
        raise ModeloDePromptInvalido(f"valor do yaml sem marcador no modelo: {sem_uso}")
    return MARCADOR.sub(lambda achado: valores[achado.group("nome")], corpo)


def _ler_modelo(config: ConfiguracaoPadroes) -> str:
    pasta = (RAIZ / PASTA_DOS_PROMPTS).resolve()
    caminho = (RAIZ / config.prompt.arquivo).resolve()
    if caminho.parent != pasta:
        raise ModeloDePromptInvalido(f"modelo precisa estar em {PASTA_DOS_PROMPTS}/")
    return caminho.read_text(encoding="utf-8")


def montar_prompt(
    config: ConfiguracaoPadroes,
    idioma: str,
    familia: str,
    vaga: str,
    blocos: Blocos,
    inventario: Inventario,
    modelo: str | None = None,
) -> PromptMontado:
    valores = _valores(config, idioma, familia, vaga, blocos, inventario)
    bruto = modelo if modelo is not None else _ler_modelo(config)
    cabecalho = CABECALHO.match(bruto)
    if cabecalho is None:
        raise ModeloDePromptInvalido("modelo sem versao no cabecalho")
    texto = _renderizar(bruto[cabecalho.end() :], valores)
    return PromptMontado(
        texto=texto,
        versao=int(cabecalho.group("versao")),
        sha256=hashlib.sha256(texto.encode("utf-8")).hexdigest(),
    )
