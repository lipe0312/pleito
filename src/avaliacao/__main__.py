from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psycopg

from src.avaliacao.configuracao import ConfiguracaoAvaliacao, configuracao_avaliacao
from src.avaliacao.conjunto import Conteudo, Entrada, lotes_do_conjunto
from src.avaliacao.referencia import Transporte, resposta_de_referencia, transporte_fixo
from src.avaliacao.relatorio import gravar_relatorio, resumo
from src.avaliacao.runner import APROVADO, avaliar
from src.config import ambiente, carregar
from src.db.conexao import ConfiguracaoBancoInvalida
from src.db.flags import SistemaDesativado
from src.gerador.configuracao import configuracao_gerador

INTERRUPCOES = (SistemaDesativado, ConfiguracaoBancoInvalida, psycopg.Error, httpx.HTTPError)


def _fabrica_offline(config: ConfiguracaoAvaliacao):
    gerador = configuracao_gerador()

    def fabrica(entrada: Entrada, conteudo: Conteudo) -> Transporte:
        resposta = resposta_de_referencia(conteudo, entrada.idioma, gerador)
        return transporte_fixo(resposta, config.offline.tokens_entrada, config.offline.tokens_saida)

    return fabrica


def main(argv: list[str] | None = None, pasta_dados: Path | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.avaliacao")
    parser.add_argument("--tier", required=True)
    parser.add_argument("--real", action="store_true")
    args = parser.parse_args(argv)
    config = configuracao_avaliacao()
    modelos = carregar("modelos")
    if args.tier not in modelos.get("tiers", {}):
        print(f"tier desconhecido: {args.tier}", file=sys.stderr)
        return 2
    pasta_dados = pasta_dados or ambiente().dados
    lotes, vagas_sem_conteudo = lotes_do_conjunto(config, pasta_dados)
    agora = datetime.now(UTC)
    fabrica = None if args.real else _fabrica_offline(config)
    try:
        relatorio = avaliar(args.tier, lotes, config, modelos, agora, fabrica, vagas_sem_conteudo)
    except INTERRUPCOES as erro:
        print(f"avaliacao interrompida: {type(erro).__name__}", file=sys.stderr)
        return 2
    caminho = gravar_relatorio(relatorio, pasta_dados, config, agora)
    print("\n".join(resumo(relatorio, caminho)))
    return 0 if relatorio["veredito"] == APROVADO else 1


if __name__ == "__main__":
    sys.exit(main())
