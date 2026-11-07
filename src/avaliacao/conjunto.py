from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.avaliacao.configuracao import ConfiguracaoAvaliacao
from src.config import RAIZ
from src.conteudo.arquivo import ler_blocos, ler_inventario
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.decompor import decompor
from src.conteudo.modelo import Blocos, Estrito, Identificador, Inventario, TextoNaoVazio
from src.gerador.configuracao import configuracao_gerador
from src.gerador.erros import TravadoInvalido
from src.gerador.travado import Travado, carregar_travado


class Entrada(Estrito):
    id: Identificador
    tipo: Identificador
    idioma: Identificador
    familia: Identificador
    empresa: TextoNaoVazio
    titulo: str = ""
    texto: TextoNaoVazio
    proibidos: list[TextoNaoVazio] = []


@dataclass(frozen=True, slots=True)
class Conteudo:
    blocos: Blocos
    inventario: Inventario
    travado: Travado


@dataclass(frozen=True, slots=True)
class Lote:
    conteudo: Conteudo
    entradas: tuple[Entrada, ...]
    vagas_reais: bool


def carregar_entradas(pasta: Path, tipo: str | None = None) -> list[Entrada]:
    entradas = []
    for caminho in sorted(pasta.glob("*.yaml")):
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
        dados["id"] = caminho.stem
        if tipo is not None:
            dados["tipo"] = tipo
        entradas.append(Entrada.model_validate(dados))
    return entradas


def conteudo_ficticio(config: ConfiguracaoAvaliacao) -> Conteudo:
    guia = (RAIZ / config.armadilhas.guia).read_text(encoding="utf-8")
    blocos, inventario = decompor(guia, configuracao_conteudo())
    bruto = yaml.safe_load((RAIZ / config.armadilhas.travado).read_text(encoding="utf-8"))
    return Conteudo(blocos, inventario, Travado.model_validate(bruto))


def conteudo_real(pasta_dados: Path) -> Conteudo | None:
    config = configuracao_conteudo()
    blocos = ler_blocos(pasta_dados, config)
    inventario = ler_inventario(pasta_dados, config)
    if blocos is None or inventario is None:
        return None
    try:
        travado = carregar_travado(pasta_dados, config, configuracao_gerador())
    except TravadoInvalido:
        return None
    return Conteudo(blocos, inventario, travado)


def lotes_do_conjunto(config: ConfiguracaoAvaliacao, pasta_dados: Path) -> tuple[list[Lote], int]:
    lotes = [
        Lote(
            conteudo_ficticio(config),
            tuple(carregar_entradas(RAIZ / config.armadilhas.pasta)),
            False,
        )
    ]
    pasta_vagas = pasta_dados / config.vagas_reais.subpasta
    vagas = carregar_entradas(pasta_vagas, config.vagas_reais.tipo) if pasta_vagas.is_dir() else []
    if not vagas:
        return lotes, 0
    conteudo = conteudo_real(pasta_dados)
    if conteudo is None:
        return lotes, len(vagas)
    lotes.append(Lote(conteudo, tuple(vagas), True))
    return lotes, 0


def versao_do_conjunto(config: ConfiguracaoAvaliacao, lotes: list[Lote]) -> str:
    entradas = sorted(
        (entrada.model_dump(mode="json") for lote in lotes for entrada in lote.entradas),
        key=lambda dados: (dados["tipo"], dados["id"]),
    )
    resumo = hashlib.sha256(
        json.dumps(entradas, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"v{config.versao_conjunto}-{resumo[:12]}"
