from __future__ import annotations

from viabilidade.contratos import MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import ColetorHttp, registrar

LISTAGEM = "https://vagas.solides.com.br/"
PAGINA_TOS = "https://solides.com.br/termos-de-uso/"


@registrar
class FonteSolides(ColetorHttp):
    slug = "solides"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        resultado.requer_revisao_tos = True
        resultado.evidencia["tos"] = PAGINA_TOS
        resultado.evidencia["aviso"] = (
            "sem API publica conhecida, veredito depende de robots e de HTML estavel"
        )
        if not self._preparar(resultado, LISTAGEM):
            return
        resposta = self._buscar(LISTAGEM)
        resultado.http_status = resposta.status_code
        resultado.evidencia["tamanho_html"] = len(resposta.text)
        resultado.evidencia["renderizado_por_js"] = "__NEXT_DATA__" in resposta.text
        if resposta.status_code in (401, 403):
            resultado.motivos.append(MotivoNoGo.EXIGE_LOGIN)
            return
        if resposta.status_code != 200:
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
            return
        resultado.motivos.append(MotivoNoGo.SEM_DADOS)
        resultado.evidencia["proximo_passo"] = (
            "extrair via navegador se robots permitir, ver docs/viabilidade.md"
        )
