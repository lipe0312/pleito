from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from src.config import RAIZ
from src.conteudo.modelo import Inventario
from src.conteudo.tecnologias import limpar_texto, texto_da_pagina
from src.padroes.configuracao import PASTA_DOS_PROMPTS, ConfiguracaoPadroes, Marcacao
from src.padroes.prompt import CABECALHO, MARCADOR, ModeloDePromptInvalido
from src.triagem.configuracao import ConfiguracaoTriagem
from src.triagem.contratos import VagaTriagem

SEPARADOR_DE_LISTA = ", "
IDIOMA_DOS_FOCOS = "pt"


@dataclass(frozen=True, slots=True)
class PromptDePontuacao:
    texto: str
    versao: int
    sha256_modelo: str
    sha256_entrada: str


def texto_externo_limpo(bruto: str, max_chars: int, marcacao: Marcacao) -> str:
    visivel, _ = texto_da_pagina(bruto, len(bruto))
    texto = limpar_texto(visivel, max_chars)
    marcas = re.compile("|".join(re.escape(m) for m in (marcacao.abre, marcacao.fecha)))
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = marcas.sub(marcacao.neutro, texto)
    return texto[:max_chars]


def _equivalencias(inventario: Inventario) -> str:
    linhas = [f"- {e.pedido} -> {e.tem}" for e in inventario.equivalencias]
    return "\n".join(linhas) if linhas else "- nenhuma"


def _familias(padroes: ConfiguracaoPadroes) -> str:
    return "\n".join(
        f"- {nome}: {SEPARADOR_DE_LISTA.join(focos[IDIOMA_DOS_FOCOS])}"
        for nome, focos in padroes.foco_sobre.items()
    )


def _valores(
    vaga: VagaTriagem,
    inventario: Inventario,
    config: ConfiguracaoTriagem,
    padroes: ConfiguracaoPadroes,
) -> dict[str, str]:
    marcacao = padroes.marcacao
    regras = config.pontuacao_final
    return {
        "inventario": SEPARADOR_DE_LISTA.join(item.tech for item in inventario.techs),
        "equivalencias": _equivalencias(inventario),
        "familias": _familias(padroes),
        "marca_abre": marcacao.abre,
        "marca_fecha": marcacao.fecha,
        "marca_neutra": marcacao.neutro,
        "idiomas": SEPARADOR_DE_LISTA.join(padroes.idiomas),
        "techs_max": str(regras.techs_max),
        "requisitos_max": str(regras.requisitos_max),
        "alertas": SEPARADOR_DE_LISTA.join(regras.alertas),
        "justificativa_max_chars": str(regras.justificativa_max_chars),
        "titulo": texto_externo_limpo(vaga.titulo, regras.titulo_max_chars, marcacao),
        "vaga": texto_externo_limpo(vaga.descricao, config.descricao_max_chars, marcacao),
    }


def _renderizar(corpo: str, valores: dict[str, str]) -> str:
    usados = {achado.group("nome") for achado in MARCADOR.finditer(corpo)}
    desconhecidos = sorted(usados - set(valores))
    if desconhecidos:
        raise ModeloDePromptInvalido(f"marcador desconhecido no modelo: {desconhecidos}")
    sem_uso = sorted(set(valores) - usados)
    if sem_uso:
        raise ModeloDePromptInvalido(f"valor sem marcador no modelo: {sem_uso}")
    return MARCADOR.sub(lambda achado: valores[achado.group("nome")], corpo)


def _ler_modelo(config: ConfiguracaoTriagem) -> str:
    pasta = (RAIZ / PASTA_DOS_PROMPTS).resolve()
    caminho = (RAIZ / config.pontuacao_final.prompt).resolve()
    if caminho.parent != pasta:
        raise ModeloDePromptInvalido(f"modelo precisa estar em {PASTA_DOS_PROMPTS}/")
    return caminho.read_text(encoding="utf-8")


def montar_prompt_de_pontuacao(
    vaga: VagaTriagem,
    inventario: Inventario,
    config: ConfiguracaoTriagem,
    padroes: ConfiguracaoPadroes,
    modelo: str | None = None,
) -> PromptDePontuacao:
    bruto = modelo if modelo is not None else _ler_modelo(config)
    cabecalho = CABECALHO.match(bruto)
    if cabecalho is None:
        raise ModeloDePromptInvalido("modelo sem versao no cabecalho")
    corpo = bruto[cabecalho.end() :]
    texto = _renderizar(corpo, _valores(vaga, inventario, config, padroes))
    return PromptDePontuacao(
        texto=texto,
        versao=int(cabecalho.group("versao")),
        sha256_modelo=hashlib.sha256(corpo.encode("utf-8")).hexdigest(),
        sha256_entrada=hashlib.sha256(texto.encode("utf-8")).hexdigest(),
    )
