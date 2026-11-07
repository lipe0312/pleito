from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from src.avaliacao.configuracao import ConfiguracaoAvaliacao

PERMISSAO_ARQUIVO = 0o600
PERMISSAO_PASTA = 0o700
ABERTURA_EXCLUSIVA = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


class RelatorioForaDeDados(ValueError):
    pass


def pasta_relatorios(pasta_dados: Path, config: ConfiguracaoAvaliacao) -> Path:
    base = pasta_dados.resolve()
    subpasta = Path(config.relatorios.subpasta)
    destino = (base / subpasta).resolve()
    if subpasta.is_absolute() or destino == base or not destino.is_relative_to(base):
        raise RelatorioForaDeDados(f"relatorio de avaliacao so pode ir para {base}")
    return destino


def gravar_relatorio(
    relatorio: dict, pasta_dados: Path, config: ConfiguracaoAvaliacao, agora: datetime
) -> Path:
    pasta = pasta_relatorios(pasta_dados, config)
    pasta.mkdir(parents=True, exist_ok=True, mode=PERMISSAO_PASTA)
    nome = f"{agora:%Y%m%dT%H%M%S}_{relatorio['tier']}_{relatorio['modo']}.json"
    caminho = pasta / nome
    descritor = os.open(caminho, ABERTURA_EXCLUSIVA, PERMISSAO_ARQUIVO)
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        json.dump(relatorio, arquivo, ensure_ascii=False, indent=2)
    return caminho


def resumo(relatorio: dict, caminho: Path) -> list[str]:
    linhas = [
        f"tier {relatorio['tier']} ({relatorio['modelo']}), modo {relatorio['modo']}: "
        f"{relatorio['veredito']}",
        f"conjunto {relatorio['versao_conjunto']}, execucoes {relatorio['execucoes']}, "
        f"taxa de aprovacao {relatorio['taxa_aprovacao']:.0%}",
        f"custo US$ {relatorio['custo_usd']} em {relatorio['chamadas']} chamadas",
    ]
    for item in relatorio["armadilhas"]:
        estado = "ok" if item["aprovada"] else "falhou: " + ", ".join(item["falhas"])
        linhas.append(f"  {item['tipo']} ({item['id']}): {estado}")
    linhas += [f"  motivo: {motivo}" for motivo in relatorio["motivos"]]
    linhas.append(f"relatorio: {caminho}")
    return linhas
