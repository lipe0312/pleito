from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.triagem.configuracao import Normalizacao
from src.triagem.contratos import VagaTriagem

NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")
PREFIXO_WWW = "www."


@dataclass(frozen=True, slots=True)
class ChaveDaVaga:
    hash: str | None
    url: str


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return NAO_ALFANUMERICO.sub(" ", sem_acento.casefold()).strip()


def _e_rastreio(nome: str, config: Normalizacao) -> bool:
    baixo = nome.lower()
    return baixo in config.parametros_rastreio or any(
        baixo.startswith(prefixo) for prefixo in config.parametros_rastreio_prefixos
    )


def url_canonica(url: str, config: Normalizacao) -> str:
    partes = urlsplit(url.strip())
    host = (partes.hostname or "").lower().removeprefix(PREFIXO_WWW)
    porta = f":{partes.port}" if partes.port else ""
    parametros = sorted(
        (nome, valor)
        for nome, valor in parse_qsl(partes.query, keep_blank_values=True)
        if not _e_rastreio(nome, config)
    )
    caminho = partes.path.rstrip("/")
    return urlunsplit((partes.scheme.lower(), host + porta, caminho, urlencode(parametros), ""))


def chave_da_vaga(vaga: VagaTriagem, config: Normalizacao) -> ChaveDaVaga:
    empresa = normalizar(vaga.empresa)
    url = url_canonica(vaga.url, config)
    if not empresa:
        return ChaveDaVaga(hash=None, url=url)
    bruto = f"{empresa}|{normalizar(vaga.titulo)}|{normalizar(vaga.local)}"
    return ChaveDaVaga(hash=hashlib.sha256(bruto.encode("utf-8")).hexdigest(), url=url)
