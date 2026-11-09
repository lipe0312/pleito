from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urlparse

import httpx

from src.coletor.base import ColetorHttp
from src.coletor.conformidade import (
    DominioNaoPermitido,
    TermosNaoPermitem,
    consultar_robots,
    exigir_termos_permitidos,
    host_permitido,
)
from src.coletor.contratos import MotivoNoGo, ResultadoColeta, VagaBruta
from src.config import carregar


@dataclass(slots=True)
class ConsultaAts:
    identificador: str
    status: int | None = None
    vagas: list[VagaBruta] = field(default_factory=list)
    erro: str | None = None
    robots_bloqueou: bool = False
    descartadas: int = 0


def identificador_valido(identificador: str) -> bool:
    return bool(re.fullmatch(carregar("fontes")["ats"]["identificador_padrao"], identificador))


def data_iso(bruto: str | None) -> date | None:
    if not bruto:
        return None
    try:
        return datetime.fromisoformat(str(bruto).replace("Z", "+00:00")).date()
    except ValueError:
        return None


class ColetorAts(ColetorHttp):
    _descartes = 0

    def _config(self) -> dict:
        return carregar("fontes")["fontes"][self.slug]

    def _url(self, identificador: str) -> str:
        return self._config()["endpoint"].format(identificador=identificador)

    def _traduzir(self, identificador: str, resposta: httpx.Response) -> list[VagaBruta]:
        raise NotImplementedError

    def _url_no_dominio(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().split(":")[0]
        return host_permitido(host, frozenset(self._config().get("dominios", [])))

    def alvos(self) -> list[str]:
        return [
            alvo
            for empresa in carregar("fontes").get("empresas_alvo") or []
            if (alvo := (empresa.get("ats") or {}).get(self.slug))
        ]

    def consultar(self, identificador: str) -> ConsultaAts:
        consulta = ConsultaAts(identificador)
        self._descartes = 0
        if not identificador_valido(identificador):
            consulta.erro = "identificador fora do padrao de config/fontes.yaml"
            return consulta
        url = self._url(identificador)
        try:
            if self._config().get("verificar_robots", True):
                if not consultar_robots(url, self._client).permitido:
                    consulta.robots_bloqueou = True
                    consulta.erro = "robots.txt proibe"
                    return consulta
            resposta = self._buscar(url)
            consulta.status = resposta.status_code
            if resposta.status_code != 200:
                consulta.erro = f"status {resposta.status_code}"
                return consulta
            consulta.vagas = self._traduzir(identificador, resposta)
            consulta.descartadas = self._descartes
        except DominioNaoPermitido as exc:
            consulta.erro = str(exc)
        except httpx.HTTPError as exc:
            consulta.erro = f"{type(exc).__name__}: {exc}"
        except ValueError as exc:
            consulta.erro = str(exc)
        return consulta

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        falhas: dict[str, str] = {}
        empresas: dict[str, int] = {}
        resultado.evidencia["empresas"] = empresas
        resultado.evidencia["falhas"] = falhas
        alvos = self.alvos()
        for identificador in alvos:
            if len(resultado.vagas) >= limite:
                break
            consulta = self.consultar(identificador)
            if consulta.status is not None:
                resultado.http_status = consulta.status
            if consulta.robots_bloqueou:
                resultado.robots_permite = False
                resultado.motivos.append(MotivoNoGo.ROBOTS_PROIBE)
            elif resultado.robots_permite is None:
                resultado.robots_permite = True
            if consulta.erro:
                falhas[identificador] = consulta.erro
                continue
            if consulta.descartadas:
                falhas[identificador] = (
                    f"{consulta.descartadas} vaga(s) descartada(s): url fora do dominio da fonte"
                )
            empresas[identificador] = len(consulta.vagas)
            resultado.vagas.extend(consulta.vagas[: limite - len(resultado.vagas)])
        so_429 = all(e == "status 429" for e in falhas.values())
        if falhas and not resultado.vagas and so_429:
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)


def exigir_ats_liberado(slug: str) -> bool:
    try:
        exigir_termos_permitidos(slug)
    except TermosNaoPermitem:
        return False
    return True
