from __future__ import annotations

import html
import re

from viabilidade.contratos import MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import (
    ColetorHttp,
    inferir_modelo,
    inferir_pais,
    inferir_senioridade,
    registrar,
)
from viabilidade.ingest.greenhouse import limpar_html

BUSCA = "https://hn.algolia.com/api/v1/search_by_date?query=%22Ask%20HN%3A%20Who%20is%20hiring%3F%22&tags=story&hitsPerPage=3"
ITEM = "https://hn.algolia.com/api/v1/items/{id}"
URL_VAGA = re.compile(r"https?://[^\s<>\"]+")
SEPARADOR = re.compile(r"\s*\|\s*")


def separar_cabecalho(texto: str) -> tuple[str, str, str]:
    primeira = texto.split("\n")[0].strip()
    partes = [p.strip() for p in SEPARADOR.split(primeira) if p.strip()]
    if len(partes) < 2:
        return "", "", primeira
    empresa = partes[0]
    titulo = next((p for p in partes[1:] if len(p) > 3), partes[1])
    return empresa, titulo, primeira


@registrar
class FonteHackerNews(ColetorHttp):
    slug = "hackernews"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        resultado.evidencia["natureza"] = "comentario em texto livre, sem campo estruturado"
        if not self._preparar(resultado, BUSCA):
            return
        busca = self._buscar(BUSCA)
        resultado.http_status = busca.status_code
        if busca.status_code != 200:
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
            return

        historias = [
            h for h in busca.json().get("hits", [])
            if "who is hiring" in (h.get("title", "") or "").lower()
        ]
        if not historias:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
            return

        historia = historias[0]
        resultado.evidencia["thread"] = historia.get("title")
        detalhe = self._buscar(ITEM.format(id=historia["objectID"]))
        if detalhe.status_code != 200:
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
            return

        filhos = detalhe.json().get("children", [])
        resultado.evidencia["comentarios"] = len(filhos)
        for filho in filhos:
            if len(resultado.vagas) >= limite:
                break
            bruto = filho.get("text") or ""
            if not bruto:
                continue
            legivel = html.unescape(bruto)
            texto = limpar_html(legivel.replace("<p>", "\n"))
            empresa, titulo, cabecalho = separar_cabecalho(texto)
            if not titulo:
                continue
            achadas = URL_VAGA.findall(legivel)
            alvo = next((u for u in achadas if u.startswith("https://")), "")
            if not alvo:
                continue
            vaga = self._vaga(
                id_externo=str(filho.get("id", "")),
                url=alvo.rstrip(".,);"),
                titulo=titulo[:200],
                empresa=empresa[:120] or "desconhecida",
                descricao=texto,
                local=cabecalho[:200],
                pais=inferir_pais(cabecalho),
                senioridade=inferir_senioridade(f"{titulo} {texto[:600]}"),
                modelo=inferir_modelo(cabecalho),
            )
            if vaga:
                resultado.vagas.append(vaga)
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
