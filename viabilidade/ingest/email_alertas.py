from __future__ import annotations

import re
from datetime import date

from viabilidade.contratos import ResultadoColeta, VagaBruta
from viabilidade.ingest.base import inferir_modelo, inferir_pais, inferir_senioridade

REMETENTES_LINKEDIN = ("jobs-noreply@linkedin.com", "jobalerts-noreply@linkedin.com")
LINK_VAGA = re.compile(r"https://www\.linkedin\.com/comm/jobs/view/(\d+)[^\s\"'<>]*")
BLOCO = re.compile(
    r"(?P<titulo>[^\n<>]{5,120})\n(?P<empresa>[^\n<>]{2,120})\n(?P<local>[^\n<>]{2,120})",
    re.MULTILINE,
)


def remetente_confiavel(remetente: str) -> bool:
    return any(r in (remetente or "").lower() for r in REMETENTES_LINKEDIN)


def extrair_alerta_linkedin(
    remetente: str,
    corpo: str,
    recebido_em: date | None = None,
) -> list[VagaBruta]:
    if not remetente_confiavel(remetente):
        return []

    vagas: list[VagaBruta] = []
    vistos: set[str] = set()
    for achado in LINK_VAGA.finditer(corpo):
        id_vaga = achado.group(1)
        if id_vaga in vistos:
            continue
        vistos.add(id_vaga)

        contexto = corpo[max(0, achado.start() - 400) : achado.start()]
        linhas = [linha.strip() for linha in contexto.split("\n") if linha.strip()]
        titulo = linhas[-3] if len(linhas) >= 3 else (linhas[-1] if linhas else "")
        empresa = linhas[-2] if len(linhas) >= 2 else "desconhecida"
        local = linhas[-1] if linhas else ""

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
                    pais=inferir_pais(local),
                    senioridade=inferir_senioridade(titulo),
                    modelo=inferir_modelo(f"{titulo} {local}"),
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
        achadas = extrair_alerta_linkedin(remetente, corpo)
        if not achadas and not remetente_confiavel(remetente):
            descartados += 1
        resultado.vagas.extend(achadas)
    resultado.evidencia["emails_descartados_por_remetente"] = descartados
    return resultado
