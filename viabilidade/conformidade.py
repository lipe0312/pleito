from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from viabilidade.config import ambiente, carregar


class DominioNaoPermitido(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DecisaoRobots:
    url: str
    permitido: bool
    robots_encontrado: bool
    crawl_delay: float | None
    detalhe: str


def dominios_permitidos() -> frozenset[str]:
    fontes = carregar("fontes").get("fontes", {})
    return frozenset(
        d for f in fontes.values() for d in f.get("dominios", []) if isinstance(d, str)
    )


def host_permitido(host: str, permitidos: frozenset[str]) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in permitidos)


def exigir_dominio_permitido(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    if not host_permitido(host, dominios_permitidos()):
        raise DominioNaoPermitido(f"{host} nao esta em config/fontes.yaml")
    return host


def consultar_robots(url: str, client: httpx.Client | None = None) -> DecisaoRobots:
    env = ambiente()
    partes = urlparse(url)
    robots_url = f"{partes.scheme}://{partes.netloc}/robots.txt"
    proprio = client is None
    client = client or httpx.Client(timeout=env.timeout, headers={"User-Agent": env.user_agent})
    try:
        resposta = client.get(robots_url)
    except httpx.HTTPError as exc:
        if proprio:
            client.close()
        return DecisaoRobots(url, False, False, None, f"robots inacessivel: {exc}")
    finally:
        if proprio and not client.is_closed:
            client.close()

    codigo = resposta.status_code
    if codigo == 429 or codigo >= 500:
        return DecisaoRobots(
            url, False, False, None, f"robots inacessivel (status {codigo}), RFC 9309 manda recusar"
        )
    if 400 <= codigo < 500:
        return DecisaoRobots(
            url, True, False, None, f"robots indisponivel (status {codigo}), RFC 9309 libera"
        )
    if codigo != 200:
        return DecisaoRobots(url, False, False, None, f"robots status inesperado {codigo}")

    parser = RobotFileParser()
    parser.parse(resposta.text.splitlines())
    permitido = parser.can_fetch(env.user_agent, url)
    atraso = parser.crawl_delay(env.user_agent)
    return DecisaoRobots(
        url=url,
        permitido=bool(permitido),
        robots_encontrado=True,
        crawl_delay=float(atraso) if atraso else None,
        detalhe="permitido por robots.txt" if permitido else "bloqueado por robots.txt",
    )


class Limitador:
    def __init__(self, rps: float) -> None:
        self._intervalo = 1.0 / rps if rps > 0 else 0.0
        self._ultimo = 0.0

    def esperar(self) -> None:
        if self._intervalo <= 0:
            return
        decorrido = time.monotonic() - self._ultimo
        if decorrido < self._intervalo:
            time.sleep(self._intervalo - decorrido)
        self._ultimo = time.monotonic()
