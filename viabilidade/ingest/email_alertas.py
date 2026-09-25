from __future__ import annotations

import re
from datetime import date

from viabilidade.contratos import ResultadoColeta, VagaBruta
from viabilidade.ingest.base import inferir_modelo, inferir_pais, inferir_senioridade
from viabilidade.triagem import extrair_anos_experiencia, inferir_funcao

CAIXAS_LINKEDIN = frozenset(
    {"jobs-noreply", "jobalerts-noreply", "jobs-listings", "jobs-noreply-comm"}
)
DOMINIO_LINKEDIN = "linkedin.com"
ENDERECO = re.compile(r"<([^>]+)>\s*$")
LINK_VAGA = re.compile(r"https://www\.linkedin\.com/comm/jobs/view/(\d+)")
ROTULOS_LINK = ("visualizar vaga", "view job", "ver vaga", "see job")
RUIDO = ("ver todas as vagas", "pesquisar", "cancelar inscricao", "ajuda", "search-results")


def endereco_de(remetente: str) -> str:
    bruto = (remetente or "").strip().lower()
    achado = ENDERECO.search(bruto)
    return (achado.group(1) if achado else bruto).strip()


def remetente_confiavel(remetente: str) -> bool:
    endereco = endereco_de(remetente)
    if endereco.count("@") != 1:
        return False
    caixa, _, dominio = endereco.partition("@")
    if dominio != DOMINIO_LINKEDIN:
        return False
    return caixa in CAIXAS_LINKEDIN


def _limpar(linha: str) -> str:
    return re.sub(r"\s+", " ", linha).strip()


def extrair_alerta_linkedin(
    remetente: str,
    corpo: str,
    recebido_em: date | None = None,
) -> list[VagaBruta]:
    if not remetente_confiavel(remetente):
        return []

    linhas = [_limpar(linha) for linha in corpo.split("\n")]
    vagas: list[VagaBruta] = []
    vistos: set[str] = set()

    for i, linha in enumerate(linhas):
        achado = LINK_VAGA.search(linha)
        if not achado:
            continue
        baixo = linha.lower()
        if not any(r in baixo for r in ROTULOS_LINK):
            continue

        id_vaga = achado.group(1)
        if id_vaga in vistos:
            continue

        anteriores = [x for x in linhas[max(0, i - 6) : i] if x and not x.startswith("---")]
        if len(anteriores) < 3:
            continue
        titulo, empresa, local = anteriores[-3], anteriores[-2], anteriores[-1]
        if any(r in titulo.lower() for r in RUIDO):
            continue

        vistos.add(id_vaga)
        contexto = f"{titulo} {local}"
        try:
            vagas.append(
                VagaBruta(
                    fonte="linkedin_alertas",
                    id_externo=id_vaga,
                    url=f"https://www.linkedin.com/jobs/view/{id_vaga}",
                    titulo=titulo[:200],
                    empresa=empresa[:120] or "desconhecida",
                    descricao="",
                    local=local[:120],
                    pais=inferir_pais(local) or "BR",
                    senioridade=inferir_senioridade(titulo),
                    modelo=inferir_modelo(contexto),
                    funcao=inferir_funcao(titulo),
                    anos_experiencia=extrair_anos_experiencia(titulo),
                    publicada_em=recebido_em,
                )
            )
        except ValueError:
            continue
    return vagas


def coletar_de_emails(emails: list[tuple[str, str]]) -> ResultadoColeta:
    resultado = ResultadoColeta(fonte="linkedin_alertas")
    resultado.robots_permite = None
    resultado.evidencia["caminho"] = "email de alerta no Gmail, o site nunca e automatizado"
    resultado.evidencia["emails_lidos"] = len(emails)
    descartados = 0
    for remetente, corpo in emails:
        if not remetente_confiavel(remetente):
            descartados += 1
            continue
        resultado.vagas.extend(extrair_alerta_linkedin(remetente, corpo))
    resultado.evidencia["emails_descartados_por_remetente"] = descartados
    return resultado
