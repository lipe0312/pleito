from __future__ import annotations

from collections.abc import Collection
from urllib.parse import urlsplit

import httpx

from src.coletor.conformidade import Limitador, consultar_robots, host_permitido

PORTA_HTTPS = 443


class LeituraRecusada(Exception):
    pass


class ForaDaAllowlist(LeituraRecusada):
    pass


class RobotsProibe(LeituraRecusada):
    pass


class LimiteDeRequisicoes(LeituraRecusada):
    pass


class RespostaInvalida(LeituraRecusada):
    pass


class Leitor:
    def __init__(
        self,
        client: httpx.Client,
        limitador: Limitador,
        requisicoes_max: int,
        resposta_max_bytes: int,
    ) -> None:
        self._client = client
        self._limitador = limitador
        self._requisicoes_max = requisicoes_max
        self._resposta_max_bytes = resposta_max_bytes
        self.requisicoes = 0

    def _gastar_requisicao(self) -> None:
        if self.requisicoes >= self._requisicoes_max:
            raise LimiteDeRequisicoes(f"limite de {self._requisicoes_max} requisicoes por execucao")
        self.requisicoes += 1
        self._limitador.esperar()

    def obter(
        self,
        url: str,
        dominios: Collection[str],
        respeitar_robots: bool,
        cabecalhos: dict[str, str] | None = None,
    ) -> httpx.Response:
        partes = urlsplit(url)
        host = (partes.hostname or "").lower()
        if (
            partes.scheme != "https"
            or partes.port not in (None, PORTA_HTTPS)
            or not host_permitido(host, frozenset(dominios))
        ):
            raise ForaDaAllowlist(f"{host or url} fora da allowlist de config/conteudo.yaml")
        if respeitar_robots:
            self._gastar_requisicao()
            if not consultar_robots(url, self._client).permitido:
                raise RobotsProibe(f"robots.txt de {host} nao permite {partes.path or '/'}")
        self._gastar_requisicao()
        resposta = self._client.get(url, headers=cabecalhos, follow_redirects=False)
        if len(resposta.content) > self._resposta_max_bytes:
            raise RespostaInvalida(f"resposta de {host} maior que o limite de bytes")
        return resposta
