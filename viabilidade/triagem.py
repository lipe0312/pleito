from __future__ import annotations

import re

from viabilidade.contratos import Funcao

TERMOS_FUNCAO = {
    Funcao.ENGENHARIA: (
        "software engineer", "engenheiro de software", "desenvolvedor", "developer",
        "programador", "backend", "back-end", "frontend", "front-end", "fullstack",
        "full stack", "full-stack", "mobile", "android", "ios", "web developer",
        "swe", "software developer", "engenharia de software", "python", "java developer",
        "desenvolvimento de sistemas", "desenvolvimento de software", "desenvolvimento web",
        "firmware", "embedded", "engenheiro de computacao", "computer engineer",
    ),
    Funcao.DADOS: (
        "data engineer", "engenheiro de dados", "data scientist", "cientista de dados",
        "data analyst", "analista de dados", "analytics engineer", "machine learning",
        "ml engineer", "bi analyst", "business intelligence", "dados",
    ),
    Funcao.INFRA: (
        "devops", "sre", "site reliability", "platform engineer", "infrastructure engineer",
        "cloud engineer", "infraestrutura", "kubernetes",
    ),
    Funcao.QA: (
        "qa engineer", "quality assurance", "test engineer", "analista de teste",
        "automacao de teste", "sdet",
    ),
}

TERMOS_FORA = (
    "executivo", "comercial", "vendas", "sales", "account executive", "account manager",
    "recrut", "recursos humanos", "people", "financeiro", "contabil", "juridico", "legal",
    "marketing", "brand", "social media", "logistica", "estoque", "motorista", "auxiliar",
    "atendimento", "customer success", "customer support", "suporte ao cliente", "enfermeir",
    "administrativ", "assistente admin", "auxiliar admin",
    "mecanic", "manutencao", "maintenance", "office assistant", "secretari", "recepcion",
    "product manager", "gerente de produto", "product owner", "scrum master", "designer",
    "ux ", "ui ", "redator", "writer", "editor", "professor", "instrutor", "consultor de",
)

SIGLAS_FUNCAO = {
    Funcao.DADOS: ("bi", "etl", "ml", "nlp", "dw"),
    Funcao.INFRA: ("sre", "k8s"),
    Funcao.QA: ("qa", "sdet"),
    Funcao.ENGENHARIA: ("swe", "api"),
}

TERMOS_GENERICOS = frozenset(
    {"dados", "bi", "analytics", "python", "sql", "mobile", "android", "ios", "web developer"}
)

ANOS = re.compile(
    r"\b(\d{1,2})\s*(?:\+|\-\s*\d{1,2})?\s*(?:years?|yrs?|anos?)\b(?![^.]{0,20}old)",
    re.IGNORECASE,
)


def _tem_sigla(texto: str, siglas: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{s}\b", texto) for s in siglas)


def inferir_funcao(titulo: str, descricao: str = "") -> Funcao:
    baixo = f" {titulo.lower()} "
    for funcao, termos in TERMOS_FUNCAO.items():
        if any(t in baixo for t in termos):
            return funcao
    for funcao, siglas in SIGLAS_FUNCAO.items():
        if _tem_sigla(baixo, siglas):
            return funcao
    if any(t in baixo for t in TERMOS_FORA):
        return Funcao.OUTRA
    if "engineer" in baixo or "engenheir" in baixo:
        return Funcao.ENGENHARIA
    if "estagi" in baixo and "desenvolv" in baixo:
        return Funcao.ENGENHARIA
    corpo = (descricao or "")[:600].lower()
    for funcao, termos in TERMOS_FUNCAO.items():
        especificos = [t for t in termos if t not in TERMOS_GENERICOS]
        if any(t in corpo for t in especificos):
            return funcao
    return Funcao.INDEFINIDA


def extrair_anos_experiencia(descricao: str) -> int | None:
    if not descricao:
        return None
    achados = [int(m.group(1)) for m in ANOS.finditer(descricao[:4000])]
    plausiveis = [a for a in achados if 0 < a <= 20]
    return min(plausiveis) if plausiveis else None
