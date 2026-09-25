from __future__ import annotations

import time
from typing import Protocol

import httpx

from viabilidade.config import ambiente
from viabilidade.conformidade import Limitador, consultar_robots, exigir_dominio_permitido
from viabilidade.contratos import (
    ModeloTrabalho,
    MotivoNoGo,
    ResultadoColeta,
    Senioridade,
    VagaBruta,
)

_REGISTRO: dict[str, type[Fonte]] = {}

PALAVRAS_ESTAGIO = ("estagi", "intern", "trainee", "aprendiz")
PALAVRAS_JUNIOR = ("junior", "jr", "entry level", "entry-level")
PALAVRAS_SENIOR = ("senior", "sr", "staff", "principal", "lead", "especialista", "iii")
PALAVRAS_PLENO = ("pleno", "mid level", "mid-level", "ii")
PALAVRAS_REMOTO = ("remote", "remoto", "anywhere", "home office")
PALAVRAS_HIBRIDO = ("hybrid", "hibrido")
PALAVRAS_PRESENCIAL = ("on-site", "onsite", "presencial")


class Fonte(Protocol):
    slug: str

    def coletar(self, limite: int) -> ResultadoColeta: ...


def registrar(cls: type[Fonte]) -> type[Fonte]:
    _REGISTRO[cls.slug] = cls
    return cls


def registro() -> dict[str, type[Fonte]]:
    return dict(_REGISTRO)


def inferir_senioridade(texto: str) -> Senioridade:
    baixo = f" {texto.lower()} "
    if any(p in baixo for p in PALAVRAS_ESTAGIO):
        return Senioridade.ESTAGIO
    if any(p in baixo for p in PALAVRAS_SENIOR):
        return Senioridade.SENIOR
    if any(p in baixo for p in PALAVRAS_PLENO):
        return Senioridade.PLENO
    if any(p in baixo for p in PALAVRAS_JUNIOR):
        return Senioridade.JUNIOR
    return Senioridade.INDEFINIDA


def inferir_modelo(texto: str) -> ModeloTrabalho:
    baixo = texto.lower()
    if any(p in baixo for p in PALAVRAS_HIBRIDO):
        return ModeloTrabalho.HIBRIDO
    if any(p in baixo for p in PALAVRAS_REMOTO):
        return ModeloTrabalho.REMOTO
    if any(p in baixo for p in PALAVRAS_PRESENCIAL):
        return ModeloTrabalho.PRESENCIAL
    return ModeloTrabalho.INDEFINIDO


class ColetorHttp:
    slug = "base"
    verificar_robots = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        env = ambiente()
        self._proprio = client is None
        self._client = client or httpx.Client(
            timeout=env.timeout,
            headers={"User-Agent": env.user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )
        self._limitador = Limitador(env.rate_limit_rps)

    def fechar(self) -> None:
        if self._proprio and not self._client.is_closed:
            self._client.close()

    def _buscar(self, url: str) -> httpx.Response:
        exigir_dominio_permitido(url)
        self._limitador.esperar()
        return self._client.get(url)

    def _preparar(self, resultado: ResultadoColeta, url: str) -> bool:
        if not self.verificar_robots:
            resultado.robots_permite = None
            return True
        decisao = consultar_robots(url, self._client)
        resultado.robots_permite = decisao.permitido
        resultado.evidencia["robots"] = decisao.detalhe
        if not decisao.permitido:
            resultado.motivos.append(MotivoNoGo.ROBOTS_PROIBE)
            return False
        return True

    def coletar(self, limite: int) -> ResultadoColeta:
        resultado = ResultadoColeta(fonte=self.slug)
        inicio = time.monotonic()
        try:
            self._executar(resultado, limite)
        except httpx.HTTPError as exc:
            resultado.erro = f"{type(exc).__name__}: {exc}"
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
        except ValueError as exc:
            resultado.erro = str(exc)
        finally:
            resultado.duracao_s = round(time.monotonic() - inicio, 3)
        return resultado

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        raise NotImplementedError

    def _vaga(self, **campos) -> VagaBruta | None:
        try:
            return VagaBruta(fonte=self.slug, **campos)
        except ValueError:
            return None
