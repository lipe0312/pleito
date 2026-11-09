from __future__ import annotations

import sys
from pathlib import Path

import yaml

from src.config import ambiente
from src.conteudo.arquivo import destino_conteudo, escrever, ler_blocos, ler_inventario
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.sincronizacao import configuracao_sincronizacao
from src.conteudo.sugestoes import carregar_sugestoes
from src.validador.banco import BancoTecnologias, montar_banco
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador
from src.validador.vocabulario import Vocabulario, montar_vocabulario


def _caminho(pasta_dados: Path, nome: str) -> Path:
    return destino_conteudo(pasta_dados, configuracao_conteudo()) / nome


def caminho_do_banco(pasta_dados: Path, config: ConfiguracaoValidador | None = None) -> Path:
    config = config or configuracao_validador()
    return _caminho(pasta_dados, config.dados.arquivos.tecnologias)


def caminho_do_vocabulario(pasta_dados: Path, config: ConfiguracaoValidador | None = None) -> Path:
    config = config or configuracao_validador()
    return _caminho(pasta_dados, config.dados.arquivos.vocabulario)


def carregar_banco(
    pasta_dados: Path, config: ConfiguracaoValidador | None = None
) -> BancoTecnologias | None:
    caminho = caminho_do_banco(pasta_dados, config)
    if not caminho.is_file():
        return None
    return BancoTecnologias.model_validate(yaml.safe_load(caminho.read_text(encoding="utf-8")))


def carregar_vocabulario(
    pasta_dados: Path, config: ConfiguracaoValidador | None = None
) -> Vocabulario | None:
    caminho = caminho_do_vocabulario(pasta_dados, config)
    if not caminho.is_file():
        return None
    return Vocabulario.model_validate(yaml.safe_load(caminho.read_text(encoding="utf-8")))


def executar(pasta_dados: Path) -> int:
    conteudo = configuracao_conteudo()
    config = configuracao_validador()
    blocos = ler_blocos(pasta_dados, conteudo)
    inventario = ler_inventario(pasta_dados, conteudo)
    if blocos is None or inventario is None:
        print("blocos e inventario ausentes: rode make conteudo antes", file=sys.stderr)
        return 2
    sugestoes = carregar_sugestoes(pasta_dados, conteudo, configuracao_sincronizacao())
    banco = montar_banco(inventario, sugestoes)
    vocabulario = montar_vocabulario(blocos, config, inventario)
    destino = destino_conteudo(pasta_dados, conteudo)
    destino.mkdir(parents=True, exist_ok=True)
    caminho_banco = caminho_do_banco(pasta_dados, config)
    caminho_vocabulario = caminho_do_vocabulario(pasta_dados, config)
    escrever(caminho_banco, banco)
    escrever(caminho_vocabulario, vocabulario)
    termos = sum(
        len(t.verbos) + len(t.siglas) + len(t.termos) + len(t.projetos)
        for t in vocabulario.root.values()
    )
    print(f"{len(banco.tecnologias)} tecnologias com evidencia e {termos} termos de vocabulario")
    print(f"gravado em {caminho_banco} e {caminho_vocabulario}")
    return 0


def main() -> None:
    raise SystemExit(executar(ambiente().dados))


if __name__ == "__main__":
    main()
