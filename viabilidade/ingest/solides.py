from __future__ import annotations

import re

from viabilidade.contratos import MotivoNoGo, ResultadoColeta
from viabilidade.ingest.base import ColetorHttp, registrar

LISTAGEM = "https://vagas.solides.com.br/vagas/todas"
PAGINA_TOS = "https://solides.com.br/termos-de-uso/"
LINK_VAGA = re.compile(r'href="(/vaga/[^"]+)"')


@registrar
class FonteSolides(ColetorHttp):
    slug = "solides"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        resultado.requer_revisao_tos = True
        resultado.evidencia["tos"] = PAGINA_TOS
        if not self._preparar(resultado, LISTAGEM):
            return

        resposta = self._buscar(LISTAGEM)
        resultado.http_status = resposta.status_code
        if resposta.status_code in (401, 403):
            resultado.motivos.append(MotivoNoGo.EXIGE_LOGIN)
            return
        if resposta.status_code != 200:
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
            return

        html = resposta.text
        links = sorted(set(LINK_VAGA.findall(html)))
        resultado.evidencia["tamanho_html"] = len(html)
        resultado.evidencia["links_de_vaga_no_html"] = len(links)
        resultado.evidencia["next_data_embutido"] = "__NEXT_DATA__" in html
        resultado.evidencia["ld_json"] = "application/ld+json" in html

        if not links:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
            resultado.evidencia["conclusao"] = (
                "listagem responde 200 mas nao traz link de vaga no HTML inicial nem JSON "
                "embutido: o conteudo e montado no cliente"
            )
            resultado.evidencia["proximo_passo"] = (
                "so viavel via navegador headless, o que muda o custo e o perfil de risco; "
                "avaliar se compensa dado que a Gupy cobre o mercado brasileiro"
            )
            return

        resultado.evidencia["conclusao"] = (
            f"{len(links)} links no HTML, parser viavel sem navegador"
        )
        resultado.motivos.append(MotivoNoGo.CAMPOS_INSUFICIENTES)
