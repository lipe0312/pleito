from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.conteudo.configuracao import ConfiguracaoConteudo
from src.conteudo.modelo import Blocos, Inventario

PERMISSAO_ARQUIVO = 0o600
PERMISSAO_PASTA = 0o700
ABERTURA_EXCLUSIVA = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


class DestinoForaDeDados(ValueError):
    pass


def destino_conteudo(pasta_dados: Path, config: ConfiguracaoConteudo) -> Path:
    base = pasta_dados.resolve()
    subpasta = Path(config.subpasta)
    destino = (base / subpasta).resolve()
    if subpasta.is_absolute() or destino == base or not destino.is_relative_to(base):
        raise DestinoForaDeDados(f"conteudo do curriculo so pode ir para {base}")
    for nome in (config.arquivo_blocos, config.arquivo_inventario):
        if Path(nome).name != nome:
            raise DestinoForaDeDados(f"nome de arquivo invalido: {nome!r}")
    return destino


def _escrever(caminho: Path, modelo: BaseModel) -> None:
    texto = yaml.safe_dump(
        modelo.model_dump(mode="json"), allow_unicode=True, sort_keys=False, width=1000
    )
    temporario = caminho.with_name(f".{caminho.name}.tmp")
    temporario.unlink(missing_ok=True)
    descritor = os.open(temporario, ABERTURA_EXCLUSIVA, PERMISSAO_ARQUIVO)
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        os.chmod(temporario, PERMISSAO_ARQUIVO)
        os.replace(temporario, caminho)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise


def gravar(
    blocos: Blocos, inventario: Inventario, pasta_dados: Path, config: ConfiguracaoConteudo
) -> tuple[Path, Path]:
    destino = destino_conteudo(pasta_dados, config)
    destino.mkdir(parents=True, exist_ok=True, mode=PERMISSAO_PASTA)
    os.chmod(destino, PERMISSAO_PASTA)
    caminho_blocos = destino / config.arquivo_blocos
    caminho_inventario = destino / config.arquivo_inventario
    _escrever(caminho_blocos, blocos)
    _escrever(caminho_inventario, inventario)
    return caminho_blocos, caminho_inventario
