from __future__ import annotations

from datetime import UTC, datetime

from viabilidade.contratos import ModeloTrabalho, MotivoNoGo, ResultadoColeta, Senioridade
from viabilidade.ingest.base import (
    ColetorHttp,
    inferir_modelo,
    inferir_pais,
    inferir_senioridade,
    registrar,
)
from viabilidade.ingest.greenhouse import limpar_html


def _data_epoch(valor) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(valor), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _data_iso(valor) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


class ColetorAgregador(ColetorHttp):
    url = ""
    chave_lista: str | None = None
    atribuicao = ""

    def _itens(self, payload) -> list[dict]:
        if self.chave_lista is None:
            return [i for i in payload if isinstance(i, dict) and self._tem_vaga(i)]
        return payload.get(self.chave_lista, [])

    def _tem_vaga(self, item: dict) -> bool:
        return True

    def _traduzir(self, item: dict) -> dict | None:
        raise NotImplementedError

    def _executar(self, resultado: ResultadoColeta, limite: int) -> None:
        if self.atribuicao:
            resultado.evidencia["atribuicao_exigida"] = self.atribuicao
        if not self._preparar(resultado, self.url):
            return
        resposta = self._buscar(self.url)
        resultado.http_status = resposta.status_code
        if resposta.status_code != 200:
            resultado.motivos.append(MotivoNoGo.BLOQUEIO_HTTP)
            return
        itens = self._itens(resposta.json())
        resultado.evidencia["itens_recebidos"] = len(itens)
        for item in itens:
            if len(resultado.vagas) >= limite:
                break
            campos = self._traduzir(item)
            if not campos:
                continue
            vaga = self._vaga(**campos)
            if vaga:
                resultado.vagas.append(vaga)
        if not resultado.vagas and not resultado.motivos:
            resultado.motivos.append(MotivoNoGo.SEM_DADOS)


@registrar
class FonteRemotive(ColetorAgregador):
    slug = "remotive"
    url = "https://remotive.com/api/remote-jobs?limit=200"
    chave_lista = "jobs"

    def _traduzir(self, item: dict) -> dict | None:
        titulo = item.get("title", "")
        local = item.get("candidate_required_location", "") or ""
        descricao = limpar_html(item.get("description", ""))
        tags = " ".join(item.get("tags") or [])
        data = _data_iso(item.get("publication_date"))
        return {
            "id_externo": str(item.get("id", "")),
            "url": item.get("url", ""),
            "titulo": titulo,
            "empresa": item.get("company_name", "") or "desconhecida",
            "descricao": descricao,
            "local": local,
            "pais": inferir_pais(local),
            "senioridade": inferir_senioridade(f"{titulo} {descricao[:400]} {tags}"),
            "modelo": ModeloTrabalho.REMOTO,
            "publicada_em": data.date() if data else None,
        }


@registrar
class FonteArbeitnow(ColetorAgregador):
    slug = "arbeitnow"
    url = "https://www.arbeitnow.com/api/job-board-api"
    chave_lista = "data"

    def _traduzir(self, item: dict) -> dict | None:
        titulo = item.get("title", "")
        local = item.get("location", "") or ""
        descricao = limpar_html(item.get("description", ""))
        data = _data_epoch(item.get("created_at"))
        modelo = (
            ModeloTrabalho.REMOTO
            if item.get("remote")
            else inferir_modelo(f"{titulo} {local}")
        )
        return {
            "id_externo": str(item.get("slug", "")),
            "url": item.get("url", ""),
            "titulo": titulo,
            "empresa": item.get("company_name", "") or "desconhecida",
            "descricao": descricao,
            "local": local,
            "pais": inferir_pais(local) or "DE",
            "senioridade": inferir_senioridade(f"{titulo} {descricao[:400]}"),
            "modelo": modelo,
            "publicada_em": data.date() if data else None,
        }


@registrar
class FonteHimalayas(ColetorAgregador):
    slug = "himalayas"
    url = "https://himalayas.app/jobs/api?limit=100"
    chave_lista = "jobs"

    MAPA_SENIORIDADE = {
        "internship": Senioridade.ESTAGIO,
        "entry-level": Senioridade.JUNIOR,
        "junior": Senioridade.JUNIOR,
        "mid-level": Senioridade.PLENO,
        "senior": Senioridade.SENIOR,
        "lead": Senioridade.SENIOR,
        "director": Senioridade.SENIOR,
        "executive": Senioridade.SENIOR,
    }

    def _senioridade_declarada(self, item: dict) -> Senioridade | None:
        for bruto in item.get("seniority") or []:
            achado = self.MAPA_SENIORIDADE.get(str(bruto).strip().lower())
            if achado:
                return achado
        return None

    def _traduzir(self, item: dict) -> dict | None:
        titulo = item.get("title", "")
        descricao = limpar_html(item.get("description") or item.get("excerpt", ""))
        restricoes = ", ".join(str(r) for r in (item.get("locationRestrictions") or []))
        data = _data_epoch(item.get("pubDate"))
        declarada = self._senioridade_declarada(item)
        return {
            "id_externo": str(item.get("guid") or item.get("applicationLink", "")),
            "url": item.get("applicationLink", "") or item.get("guid", ""),
            "titulo": titulo,
            "empresa": item.get("companyName", "") or "desconhecida",
            "descricao": descricao,
            "local": restricoes or "remoto",
            "pais": inferir_pais(restricoes) or "remoto_global",
            "senioridade": declarada or inferir_senioridade(f"{titulo} {descricao[:400]}"),
            "modelo": ModeloTrabalho.REMOTO,
            "publicada_em": data.date() if data else None,
        }


@registrar
class FonteRemoteok(ColetorAgregador):
    slug = "remoteok"
    url = "https://remoteok.com/api"
    chave_lista = None
    atribuicao = "os termos da API exigem link de volta para remoteok.com em qualquer exibicao"

    def _tem_vaga(self, item: dict) -> bool:
        return bool(item.get("id") and item.get("position"))

    def _traduzir(self, item: dict) -> dict | None:
        titulo = item.get("position", "")
        local = item.get("location", "") or ""
        descricao = limpar_html(item.get("description", ""))
        tags = " ".join(item.get("tags") or [])
        data = _data_epoch(item.get("epoch"))
        return {
            "id_externo": str(item.get("id", "")),
            "url": (item.get("url") or item.get("apply_url", "")).replace("remoteOK", "remoteok"),
            "titulo": titulo,
            "empresa": item.get("company", "") or "desconhecida",
            "descricao": descricao,
            "local": local or "remoto",
            "pais": inferir_pais(local) or "remoto_global",
            "senioridade": inferir_senioridade(f"{titulo} {descricao[:400]} {tags}"),
            "modelo": ModeloTrabalho.REMOTO,
            "publicada_em": data.date() if data else None,
        }


@registrar
class FonteJobicy(ColetorAgregador):
    slug = "jobicy"
    url = "https://jobicy.com/api/v2/remote-jobs?count=50"
    chave_lista = "jobs"

    MAPA_NIVEL = {
        "internship": Senioridade.ESTAGIO,
        "junior": Senioridade.JUNIOR,
        "entry": Senioridade.JUNIOR,
        "mid": Senioridade.PLENO,
        "senior": Senioridade.SENIOR,
        "executive": Senioridade.SENIOR,
    }

    def _traduzir(self, item: dict) -> dict | None:
        titulo = item.get("jobTitle", "")
        geo = item.get("jobGeo", "") or ""
        descricao = limpar_html(item.get("jobDescription") or item.get("jobExcerpt", ""))
        data = _data_iso(item.get("pubDate"))
        nivel = str(item.get("jobLevel", "")).strip().lower()
        declarada = self.MAPA_NIVEL.get(nivel)
        return {
            "id_externo": str(item.get("id", "")),
            "url": item.get("url", ""),
            "titulo": titulo,
            "empresa": item.get("companyName", "") or "desconhecida",
            "descricao": descricao,
            "local": geo or "remoto",
            "pais": inferir_pais(geo) or "remoto_global",
            "senioridade": declarada or inferir_senioridade(f"{titulo} {descricao[:400]}"),
            "modelo": ModeloTrabalho.REMOTO,
            "publicada_em": data.date() if data else None,
        }
