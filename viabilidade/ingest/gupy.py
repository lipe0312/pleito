from __future__ import annotations

from datetime import datetime

from viabilidade.config import carregar
from viabilidade.contratos import MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import ColetorHttp, inferir_modelo, inferir_senioridade, registrar

PORTAL = "https://portal.api.gupy.io/api/v1/jobs"
PAGINA_TOS = "https://www.gupy.io/termos-de-uso"


def parse_portal(payload: dict, coletor: ColetorHttp) -> list:
    vagas = []
    for item in payload.get("data", []):
        titulo = item.get("name", "")
        empresa = (item.get("careerPageName") or item.get("companyName") or "").strip()
        local = ", ".join(p for p in (item.get("city"), item.get("state")) if p)
        publicada = None
        if item.get("publishedDate"):
            try:
                publicada = datetime.fromisoformat(
                    item["publishedDate"].replace("Z", "+00:00")
                ).date()
            except ValueError:
                publicada = None
        vaga = coletor._vaga(
            id_externo=str(item.get("id", "")),
            url=item.get("jobUrl", "") or item.get("careerPageUrl", ""),
            titulo=titulo,
            empresa=empresa or "desconhecida",
            descricao=item.get("description", "") or "",
            local=local,
            pais=item.get("country", "") or "",
            senioridade=inferir_senioridade(titulo),
            modelo=inferir_modelo(f"{titulo} {item.get('workplaceType', '')} {local}"),
            publicada_em=publicada,
        )
        if vaga:
            vagas.append(vaga)
    return vagas


@registrar
class FonteGupy(ColetorHttp):
    slug = "gupy"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        resultado.requer_revisao_tos = True
        resultado.evidencia["tos"] = PAGINA_TOS
        resultado.evidencia["aviso"] = (
            "endpoint de portal publico, uso automatizado pendente de leitura dos termos"
        )
        termos = carregar("filtros")["termos_busca"]["pt"]
        if not self._preparar(resultado, PORTAL):
            return
        for termo in termos:
            if len(resultado.vagas) >= limite:
                break
            resposta = self._buscar(f"{PORTAL}?name={termo}&limit=20")
            resultado.http_status = resposta.status_code
            if resposta.status_code in (401, 403):
                resultado.motivos.append(MotivoNoGo.EXIGE_LOGIN)
                resultado.evidencia[termo] = f"status {resposta.status_code}"
                return
            if resposta.status_code == 429:
                resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
                return
            if resposta.status_code != 200:
                resultado.evidencia[termo] = f"status {resposta.status_code}"
                continue
            encontradas = parse_portal(resposta.json(), self)
            resultado.evidencia[termo] = len(encontradas)
            resultado.vagas.extend(encontradas[: limite - len(resultado.vagas)])
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
