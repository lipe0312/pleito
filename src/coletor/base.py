from __future__ import annotations

import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx

from src.coletor.conformidade import (
    Limitador,
    TermosNaoPermitem,
    consultar_robots,
    exigir_dominio_permitido,
    exigir_termos_permitidos,
)
from src.coletor.contratos import (
    ModeloTrabalho,
    MotivoNoGo,
    ResultadoColeta,
    Senioridade,
    VagaBruta,
)
from src.config import ambiente, carregar
from src.triagem.regra import extrair_anos_experiencia, inferir_funcao

_REGISTRO: dict[str, type[Fonte]] = {}

PALAVRAS_ESTAGIO = ("estagi", "intern", "trainee", "aprendiz")
PALAVRAS_JUNIOR = ("junior", "jr", "entry level", "entry-level")
PALAVRAS_SENIOR = ("senior", "sr", "staff", "principal", "lead", "especialista", "iii")
PALAVRAS_PLENO = ("pleno", "mid level", "mid-level", "ii")
PALAVRAS_REMOTO = ("remote", "remoto", "anywhere", "home office")
PALAVRAS_HIBRIDO = ("hybrid", "hibrido")
PALAVRAS_PRESENCIAL = ("on-site", "onsite", "presencial")

PAISES = {
    "BR": (
        "brazil",
        "brasil",
        "sao paulo",
        "rio de janeiro",
        "belo horizonte",
        "salvador",
        "curitiba",
        "porto alegre",
        "recife",
        "florianopolis",
        "campinas",
        "bahia",
    ),
    "US": ("united states", "usa", "u.s.", "new york", "san francisco", "austin", "seattle"),
    "PT": ("portugal", "lisbon", "lisboa", "porto"),
    "ES": ("spain", "espanha", "madrid", "barcelona"),
    "MX": ("mexico", "mexico city", "guadalajara"),
    "AR": ("argentina", "buenos aires"),
    "CL": ("chile", "santiago"),
    "CO": ("colombia", "bogota", "medellin"),
    "UY": ("uruguay", "montevideo"),
    "PE": ("peru", "lima"),
    "CA": ("canada", "toronto", "vancouver"),
    "DE": ("germany", "alemanha", "berlin", "munich", "hamburg"),
    "GB": ("united kingdom", "london", "england"),
}
MARCAS_GLOBAL = ("worldwide", "anywhere", "global", "remote - global", "any location")


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


def inferir_pais(texto: str) -> str:
    baixo = (texto or "").lower()
    if not baixo.strip():
        return ""
    for sigla, marcas in PAISES.items():
        if any(m in baixo for m in marcas):
            return sigla
    if any(m in baixo for m in MARCAS_GLOBAL):
        return "remoto_global"
    return ""


def inferir_modelo(texto: str) -> ModeloTrabalho:
    baixo = texto.lower()
    if any(p in baixo for p in PALAVRAS_HIBRIDO):
        return ModeloTrabalho.HIBRIDO
    if any(p in baixo for p in PALAVRAS_REMOTO):
        return ModeloTrabalho.REMOTO
    if any(p in baixo for p in PALAVRAS_PRESENCIAL):
        return ModeloTrabalho.PRESENCIAL
    return ModeloTrabalho.INDEFINIDO


def _segundos_retry_after(bruto: str | None) -> float | None:
    if not bruto:
        return None
    bruto = bruto.strip()
    if bruto.isdigit():
        return float(bruto)
    try:
        data = parsedate_to_datetime(bruto)
    except (TypeError, ValueError):
        return None
    if data.tzinfo is None:
        data = data.replace(tzinfo=UTC)
    return max((data - datetime.now(UTC)).total_seconds(), 0.0)


class ColetorHttp:
    slug = "base"
    verificar_robots = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        env = ambiente()
        self._proprio = client is None
        self._client = client or httpx.Client(
            timeout=env.timeout,
            headers={"User-Agent": env.user_agent, "Accept": "application/json"},
            follow_redirects=False,
        )
        self._limitador = Limitador(env.rate_limit_rps)

    def fechar(self) -> None:
        if self._proprio and not self._client.is_closed:
            self._client.close()

    def _dormir(self, segundos: float) -> None:
        time.sleep(segundos)

    def _espera_429(self, resposta: httpx.Response, tentativa: int) -> float:
        cfg = carregar("fontes")["backoff_429"]
        teto = float(cfg["max_s"])
        espera = min(float(cfg["base_s"]) * 2**tentativa, teto)
        pedido = _segundos_retry_after(resposta.headers.get("retry-after"))
        if pedido is not None:
            espera = max(espera, min(pedido, teto))
        return espera

    def _buscar(self, url: str) -> httpx.Response:
        tentativas = int(carregar("limites")["rede"]["tentativas"])
        for tentativa in range(tentativas):
            resposta = self._buscar_uma_vez(url)
            if resposta.status_code != 429 or tentativa == tentativas - 1:
                return resposta
            self._dormir(self._espera_429(resposta, tentativa))
        return resposta

    def _buscar_uma_vez(self, url: str) -> httpx.Response:
        limite = int(carregar("limites")["rede"]["redirecionamentos_max"])
        atual = url
        for salto in range(limite + 1):
            exigir_dominio_permitido(atual)
            if salto > 0:
                if not atual.startswith("https://"):
                    raise ValueError(f"redirect para destino sem https: {atual}")
                if not consultar_robots(atual, self._client).permitido:
                    raise ValueError(f"robots.txt proibe o destino do redirect: {atual}")
            self._limitador.esperar()
            resposta = self._client.get(atual, follow_redirects=False)
            destino = resposta.headers.get("location")
            if not resposta.is_redirect or not destino:
                return resposta
            atual = str(resposta.url.join(destino))
        raise ValueError(f"redirecionamentos acima do limite de {limite}")

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
            exigir_termos_permitidos(self.slug)
        except TermosNaoPermitem as exc:
            resultado.erro = str(exc)
            resultado.motivos.append(MotivoNoGo.TOS_PROIBE)
            return resultado
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
        campos.setdefault(
            "funcao", inferir_funcao(campos.get("titulo", ""), campos.get("descricao", ""))
        )
        campos.setdefault("anos_experiencia", extrair_anos_experiencia(campos.get("descricao", "")))
        try:
            return VagaBruta(fonte=self.slug, **campos)
        except ValueError:
            return None
