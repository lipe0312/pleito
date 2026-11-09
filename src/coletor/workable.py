from __future__ import annotations

import httpx

from src.coletor.ats import ColetorAts, data_iso
from src.coletor.base import inferir_modelo, inferir_pais, inferir_senioridade, registrar
from src.coletor.contratos import VagaBruta
from src.coletor.greenhouse import limpar_html


@registrar
class FonteWorkable(ColetorAts):
    slug = "workable"

    def _traduzir(self, identificador: str, resposta: httpx.Response) -> list[VagaBruta]:
        try:
            payload = resposta.json()
        except ValueError as exc:
            raise ValueError(f"json invalido: {exc}") from exc
        empresa = payload.get("name") or identificador
        vagas = []
        for job in payload.get("jobs") or []:
            titulo = job.get("title") or ""
            local = ", ".join(
                p for p in (job.get("city"), job.get("state"), job.get("country")) if p
            )
            descricao = limpar_html(job.get("description") or "")
            tipo = job.get("employment_type") or ""
            remoto = "remote" if job.get("telecommuting") else ""
            url = job.get("url") or job.get("shortlink") or ""
            if not self._url_no_dominio(url):
                self._descartes += 1
                continue
            vaga = self._vaga(
                id_externo=str(job.get("shortcode") or job.get("id") or ""),
                url=url,
                titulo=titulo,
                empresa=empresa,
                descricao=descricao,
                local=local,
                pais=inferir_pais(local),
                senioridade=inferir_senioridade(f"{titulo} {tipo} {descricao[:400]}"),
                modelo=inferir_modelo(f"{titulo} {local} {remoto}"),
                publicada_em=data_iso(job.get("published_on") or job.get("created_at")),
            )
            if vaga:
                vagas.append(vaga)
        return vagas
