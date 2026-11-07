from __future__ import annotations

from src.triagem.configuracao import Normalizacao
from src.triagem.contratos import VagaTriagem
from src.triagem.normalizacao import chave_da_vaga


class Deduplicador:
    def __init__(self, config: Normalizacao) -> None:
        self._config = config
        self._por_hash: dict[str, int] = {}
        self._por_url: dict[str, int] = {}

    def registrar(self, vaga: VagaTriagem) -> None:
        chave = chave_da_vaga(vaga, self._config)
        if chave.hash is not None:
            self._por_hash.setdefault(chave.hash, vaga.id)
        if chave.url:
            self._por_url.setdefault(chave.url, vaga.id)

    def duplicada_de(self, vaga: VagaTriagem) -> int | None:
        chave = chave_da_vaga(vaga, self._config)
        if chave.hash is not None and chave.hash in self._por_hash:
            return self._por_hash[chave.hash]
        return self._por_url.get(chave.url)
