from __future__ import annotations

from viabilidade.config import carregar
from viabilidade.contratos import MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import ColetorHttp, inferir_modelo, inferir_senioridade, registrar
from viabilidade.ingest.greenhouse import limpar_html

API = "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=false"


def parse_board(payload: dict, board: str, coletor: ColetorHttp) -> list:
    vagas = []
    for posting in payload.get("jobs", []):
        titulo = posting.get("title", "")
        local = posting.get("location", "") or ""
        descricao = limpar_html(
            posting.get("descriptionPlain") or posting.get("descriptionHtml", "")
        )
        remoto = posting.get("isRemote")
        modelo_texto = "remote" if remoto else f"{titulo} {local}"
        vaga = coletor._vaga(
            id_externo=str(posting.get("id", "")),
            url=posting.get("jobUrl", ""),
            titulo=titulo,
            empresa=board,
            descricao=descricao,
            local=local,
            senioridade=inferir_senioridade(f"{titulo} {descricao[:400]}"),
            modelo=inferir_modelo(modelo_texto),
        )
        if vaga:
            vagas.append(vaga)
    return vagas


@registrar
class FonteAshby(ColetorHttp):
    slug = "ashby"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        boards = carregar("fontes")["fontes"]["ashby"]["boards"]
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
            encontradas = parse_board(resposta.json(), board, self)
            resultado.evidencia[board] = len(encontradas)
            resultado.vagas.extend(encontradas[: limite - len(resultado.vagas)])
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
