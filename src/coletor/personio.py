from __future__ import annotations

import httpx
from defusedxml.ElementTree import fromstring as fromstring_seguro

from src.coletor.ats import ColetorAts, data_iso
from src.coletor.base import inferir_modelo, inferir_pais, inferir_senioridade, registrar
from src.coletor.contratos import Senioridade, VagaBruta
from src.coletor.greenhouse import limpar_html

NIVEIS = {"student": Senioridade.ESTAGIO, "entry-level": Senioridade.JUNIOR}


def _texto(no, nome: str) -> str:
    filho = no.find(nome)
    return (filho.text or "").strip() if filho is not None else ""


@registrar
class FontePersonio(ColetorAts):
    slug = "personio"

    def _traduzir(self, identificador: str, resposta: httpx.Response) -> list[VagaBruta]:
        try:
            raiz = fromstring_seguro(resposta.content)
        except Exception as exc:
            raise ValueError(f"xml invalido: {exc}") from exc
        modelo_url = self._config()["url_vaga"]
        vagas = []
        for posicao in raiz.iter("position"):
            titulo = _texto(posicao, "name")
            local = _texto(posicao, "office")
            descricao = limpar_html(
                " ".join(
                    (bloco.findtext("value") or "")
                    for bloco in posicao.iter("jobDescription")
                )
            )
            nivel = _texto(posicao, "seniority")
            id_vaga = _texto(posicao, "id")
            vaga = self._vaga(
                id_externo=id_vaga,
                url=modelo_url.format(identificador=identificador, id=id_vaga),
                titulo=titulo,
                empresa=identificador,
                descricao=descricao,
                local=local,
                pais=inferir_pais(local),
                senioridade=NIVEIS.get(nivel)
                or inferir_senioridade(f"{titulo} {descricao[:400]}"),
                modelo=inferir_modelo(f"{titulo} {local} {_texto(posicao, 'schedule')}"),
                publicada_em=data_iso(_texto(posicao, "createdAt")),
            )
            if vaga:
                vagas.append(vaga)
        return vagas
