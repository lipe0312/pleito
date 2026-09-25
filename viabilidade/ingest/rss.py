from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from defusedxml.ElementTree import fromstring as fromstring_seguro

from viabilidade.contratos import ModeloTrabalho, MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import ColetorHttp, inferir_pais, inferir_senioridade, registrar
from viabilidade.ingest.greenhouse import limpar_html


def _texto(item: ET.Element, *nomes: str) -> str:
    for nome in nomes:
        for filho in item:
            if filho.tag.split("}")[-1] == nome and filho.text:
                return filho.text.strip()
    return ""


def _data(bruto: str) -> datetime | None:
    if not bruto:
        return None
    try:
        return parsedate_to_datetime(bruto)
    except (TypeError, ValueError):
        return None


class ColetorRss(ColetorHttp):
    url = ""

    def _traduzir(self, item: ET.Element) -> dict | None:
        raise NotImplementedError

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        if not self._preparar(resultado, self.url):
            return
        resposta = self._buscar(self.url)
        resultado.http_status = resposta.status_code
        if resposta.status_code != 200:
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
            return
        try:
            raiz = fromstring_seguro(resposta.content)
        except Exception as exc:
            resultado.erro = f"rss invalido: {exc}"
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
            return

        itens = raiz.findall(".//item")
        resultado.evidencia["itens_no_feed"] = len(itens)
        for item in itens:
            if len(resultado.vagas) >= limite:
                break
            campos = self._traduzir(item)
            if not campos:
                continue
            vaga = self._vaga(**campos)
            if vaga:
                resultado.vagas.append(vaga)
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)


@registrar
class FonteWeWorkRemotely(ColetorRss):
    slug = "weworkremotely"
    url = "https://weworkremotely.com/remote-jobs.rss"

    def _traduzir(self, item: ET.Element) -> dict | None:
        bruto = _texto(item, "title")
        empresa, _, titulo = bruto.partition(":")
        if not titulo:
            empresa, titulo = "desconhecida", bruto
        regiao = _texto(item, "region")
        descricao = limpar_html(_texto(item, "description"))
        categoria = _texto(item, "category")
        link = _texto(item, "link", "guid")
        data = _data(_texto(item, "pubDate"))
        return {
            "id_externo": link.rstrip("/").split("/")[-1],
            "url": link,
            "titulo": titulo.strip(),
            "empresa": empresa.strip() or "desconhecida",
            "descricao": descricao,
            "local": regiao or "remoto",
            "pais": inferir_pais(f"{regiao} {_texto(item, 'country')}") or "remoto_global",
            "senioridade": inferir_senioridade(
                f"{titulo} {descricao[:400]} {categoria}"
            ),
            "modelo": ModeloTrabalho.REMOTO,
            "publicada_em": data.date() if data else None,
        }


@registrar
class FonteJobspresso(ColetorRss):
    slug = "jobspresso"
    url = "https://jobspresso.co/?feed=job_feed"

    def _traduzir(self, item: ET.Element) -> dict | None:
        titulo = _texto(item, "title")
        empresa = _texto(item, "company") or "desconhecida"
        local = _texto(item, "location")
        descricao = limpar_html(_texto(item, "encoded", "description"))
        link = _texto(item, "link", "guid")
        data = _data(_texto(item, "pubDate"))
        return {
            "id_externo": _texto(item, "post-id") or link.rstrip("/").split("/")[-1],
            "url": link,
            "titulo": titulo,
            "empresa": empresa,
            "descricao": descricao,
            "local": local or "remoto",
            "pais": inferir_pais(local) or "remoto_global",
            "senioridade": inferir_senioridade(f"{titulo} {descricao[:400]}"),
            "modelo": ModeloTrabalho.REMOTO,
            "publicada_em": data.date() if data else None,
        }
