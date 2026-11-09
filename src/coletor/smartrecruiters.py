from __future__ import annotations

import httpx

from src.coletor.ats import ColetorAts, data_iso
from src.coletor.base import inferir_pais, inferir_senioridade, registrar
from src.coletor.contratos import ModeloTrabalho, Senioridade, VagaBruta

NIVEIS = {
    "internship": Senioridade.ESTAGIO,
    "entry_level": Senioridade.JUNIOR,
    "associate": Senioridade.PLENO,
    "mid_senior_level": Senioridade.SENIOR,
    "director": Senioridade.SENIOR,
    "executive": Senioridade.SENIOR,
}


@registrar
class FonteSmartRecruiters(ColetorAts):
    slug = "smartrecruiters"

    def _traduzir(self, identificador: str, resposta: httpx.Response) -> list[VagaBruta]:
        try:
            payload = resposta.json()
        except ValueError as exc:
            raise ValueError(f"json invalido: {exc}") from exc
        modelo_url = self._config()["url_vaga"]
        paises_iso = self._config()["paises_iso"]
        vagas = []
        for posting in payload.get("content") or []:
            titulo = posting.get("name") or ""
            local_bruto = posting.get("location") or {}
            pais_iso = str(local_bruto.get("country") or "").lower()
            local = ", ".join(p for p in (local_bruto.get("city"), pais_iso.upper()) if p)
            nivel = (posting.get("experienceLevel") or {}).get("id", "")
            senioridade = NIVEIS.get(nivel) or inferir_senioridade(titulo)
            if local_bruto.get("remote"):
                modelo = ModeloTrabalho.REMOTO
            elif local_bruto.get("hybrid"):
                modelo = ModeloTrabalho.HIBRIDO
            else:
                modelo = ModeloTrabalho.INDEFINIDO
            id_vaga = str(posting.get("id") or "")
            vaga = self._vaga(
                id_externo=id_vaga,
                url=modelo_url.format(identificador=identificador, id=id_vaga),
                titulo=titulo,
                empresa=(posting.get("company") or {}).get("name") or identificador,
                local=local,
                pais=paises_iso.get(pais_iso) or inferir_pais(local),
                senioridade=senioridade,
                modelo=modelo,
                publicada_em=data_iso(posting.get("releasedDate")),
            )
            if vaga:
                vagas.append(vaga)
        return vagas
