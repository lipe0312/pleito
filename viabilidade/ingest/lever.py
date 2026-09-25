from __future__ import annotations

from datetime import UTC, datetime

from viabilidade.config import carregar
from viabilidade.contratos import MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import ColetorHttp, inferir_modelo, inferir_senioridade, registrar
from viabilidade.ingest.greenhouse import limpar_html

API = "https://api.lever.co/v0/postings/{empresa}?mode=json"


def parse_postings(payload: list, empresa: str, coletor: ColetorHttp) -> list:
    vagas = []
    for posting in payload:
        categorias = posting.get("categories") or {}
        local = categorias.get("location", "") or ""
        titulo = posting.get("text", "")
        descricao = limpar_html(posting.get("descriptionPlain") or posting.get("description", ""))
        publicada = None
        if posting.get("createdAt"):
            try:
                publicada = datetime.fromtimestamp(
                    posting["createdAt"] / 1000, tz=UTC
                ).date()
            except (TypeError, ValueError, OSError):
                publicada = None
        vaga = coletor._vaga(
            id_externo=str(posting.get("id", "")),
            url=posting.get("hostedUrl", ""),
            titulo=titulo,
            empresa=empresa,
            descricao=descricao,
            local=local,
            senioridade=inferir_senioridade(f"{titulo} {descricao[:400]}"),
            modelo=inferir_modelo(f"{titulo} {local} {categorias.get('commitment', '')}"),
            publicada_em=publicada,
        )
        if vaga:
            vagas.append(vaga)
    return vagas


@registrar
class FonteLever(ColetorHttp):
    slug = "lever"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        empresas = carregar("fontes")["fontes"]["lever"]["empresas"]
        if not self._preparar(resultado, API.format(empresa=empresas[0])):
            return
        for empresa in empresas:
            if len(resultado.vagas) >= limite:
                break
            resposta = self._buscar(API.format(empresa=empresa))
            resultado.http_status = resposta.status_code
            if resposta.status_code != 200:
                resultado.evidencia[empresa] = f"status {resposta.status_code}"
                continue
            encontradas = parse_postings(resposta.json(), empresa, self)
            resultado.evidencia[empresa] = len(encontradas)
            resultado.vagas.extend(encontradas[: limite - len(resultado.vagas)])
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
