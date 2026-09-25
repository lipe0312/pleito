from __future__ import annotations

import re
from datetime import date, datetime

from viabilidade.config import carregar
from viabilidade.contratos import MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import ColetorHttp, inferir_modelo, inferir_senioridade, registrar

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
TAGS = re.compile(r"<[^>]+>")


def limpar_html(bruto: str) -> str:
    import html

    return html.unescape(TAGS.sub(" ", bruto or "")).replace("\xa0", " ").strip()


def parse_jobs(payload: dict, board: str, coletor: ColetorHttp) -> list:
    vagas = []
    for job in payload.get("jobs", []):
        descricao = limpar_html(job.get("content", ""))
        titulo = job.get("title", "")
        local = (job.get("location") or {}).get("name", "")
        publicada = None
        bruto_data = job.get("first_published") or job.get("updated_at")
        if bruto_data:
            try:
                publicada = datetime.fromisoformat(bruto_data.replace("Z", "+00:00")).date()
            except ValueError:
                publicada = None
        vaga = coletor._vaga(
            id_externo=str(job.get("id", "")),
            url=job.get("absolute_url", ""),
            titulo=titulo,
            empresa=board,
            descricao=descricao,
            local=local,
            senioridade=inferir_senioridade(f"{titulo} {descricao[:400]}"),
            modelo=inferir_modelo(f"{titulo} {local} {descricao[:800]}"),
            publicada_em=publicada if isinstance(publicada, date) else None,
        )
        if vaga:
            vagas.append(vaga)
    return vagas


@registrar
class FonteGreenhouse(ColetorHttp):
    slug = "greenhouse"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        boards = carregar("fontes")["fontes"]["greenhouse"]["boards"]
        if not self._preparar(resultado, API.format(board=boards[0])):
            return
        for board in boards:
            if len(resultado.vagas) >= limite:
                break
            resposta = self._buscar(API.format(board=board))
            resultado.http_status = resposta.status_code
            if resposta.status_code != 200:
                resultado.evidencia[board] = f"status {resposta.status_code}"
                continue
            encontradas = parse_jobs(resposta.json(), board, self)
            resultado.evidencia[board] = len(encontradas)
            resultado.vagas.extend(encontradas[: limite - len(resultado.vagas)])
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
