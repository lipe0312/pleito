from __future__ import annotations

from datetime import datetime

from viabilidade.config import carregar
from viabilidade.contratos import ModeloTrabalho, MotivoNoGo, ResultadoColeta, Senioridade
from viabilidade.ingest.base import ColetorHttp, inferir_senioridade, registrar

API = "https://employability-portal.gupy.io/api/v1/jobs"
PAGINA_TOS = "https://www.gupy.io/termos-de-uso"
PAGINA_POR_TERMO = 100
PAGINAS_POR_TERMO_MAX = 3

MAPA_TIPO = {
    "vacancy_type_internship": Senioridade.ESTAGIO,
    "vacancy_type_apprentice": Senioridade.ESTAGIO,
}
MAPA_LOCAL = {
    "remote": ModeloTrabalho.REMOTO,
    "hybrid": ModeloTrabalho.HIBRIDO,
    "on-site": ModeloTrabalho.PRESENCIAL,
}


def traduzir(item: dict, coletor: ColetorHttp):
    titulo = item.get("name", "")
    descricao = item.get("description", "") or ""
    local = ", ".join(p for p in (item.get("city"), item.get("state")) if p)
    publicada = None
    if item.get("publishedDate"):
        try:
            publicada = datetime.fromisoformat(item["publishedDate"].replace("Z", "+00:00")).date()
        except ValueError:
            publicada = None

    declarada = MAPA_TIPO.get(item.get("type", ""))
    modelo = MAPA_LOCAL.get(item.get("workplaceType", ""), ModeloTrabalho.INDEFINIDO)
    if modelo is ModeloTrabalho.INDEFINIDO and item.get("isRemoteWork"):
        modelo = ModeloTrabalho.REMOTO

    pais = item.get("country") or ""
    return coletor._vaga(
        id_externo=str(item.get("id", "")),
        url=item.get("jobUrl", "") or item.get("careerPageUrl", ""),
        titulo=titulo,
        empresa=(item.get("careerPageName") or "desconhecida").strip(),
        descricao=descricao,
        local=local,
        pais="BR" if pais.lower().startswith("bras") else pais,
        senioridade=declarada or inferir_senioridade(f"{titulo} {descricao[:400]}"),
        modelo=modelo,
        publicada_em=publicada,
    )


@registrar
class FonteGupy(ColetorHttp):
    slug = "gupy"

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        resultado.requer_revisao_tos = True
        resultado.evidencia["tos"] = PAGINA_TOS
        resultado.evidencia["aviso"] = (
            "API do portal de empregabilidade, publica e sem chave; uso automatizado "
            "pendente de leitura dos termos"
        )
        if not self._preparar(resultado, API):
            return

        filtros = carregar("filtros")
        termos = filtros["termos_busca"].get("gupy") or filtros["termos_busca"]["pt"]
        vistos: set[str] = set()

        for termo in termos:
            if len(resultado.vagas) >= limite:
                break
            novas = 0
            total = 0
            for pagina in range(PAGINAS_POR_TERMO_MAX):
                if len(resultado.vagas) >= limite:
                    break
                offset = pagina * PAGINA_POR_TERMO
                resposta = self._buscar(
                    f"{API}?jobName={termo}&offset={offset}&limit={PAGINA_POR_TERMO}"
                )
                resultado.http_status = resposta.status_code
                if resposta.status_code in (401, 403):
                    resultado.motivos.append(MotivoNoGo.EXIGE_LOGIN)
                    return
                if resposta.status_code == 429:
                    resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
                    return
                if resposta.status_code != 200:
                    resultado.evidencia[termo] = f"status {resposta.status_code}"
                    break

                corpo = resposta.json()
                total = (corpo.get("pagination") or {}).get("total", total)
                itens = corpo.get("data", [])
                if not itens:
                    break
                for item in itens:
                    if len(resultado.vagas) >= limite:
                        break
                    chave = str(item.get("id", ""))
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    vaga = traduzir(item, self)
                    if vaga:
                        resultado.vagas.append(vaga)
                        novas += 1
            resultado.evidencia[termo] = f"{novas} novas de {total} disponiveis"

        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)
