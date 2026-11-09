from __future__ import annotations

import copy
from dataclasses import replace

import httpx

from src.coletor import ats, base, conformidade, descoberta, rodada
from src.config import carregar as carregar_real

TERMOS_OK = {"revisado_em": "2026-11-08", "veredito": "permite_com_condicao", "link": "https://x"}
TERMOS_PENDENTES = {"veredito": "pendente", "link": "https://x"}

CONFIG_BASE = {
    "vereditos_coletaveis": ["permite", "permite_com_condicao"],
    "backoff_429": {"base_s": 2, "max_s": 30},
    "ats": {
        "fontes": ["workable", "smartrecruiters", "personio"],
        "identificador_padrao": "^[A-Za-z0-9_-]{1,64}$",
        "candidatos_max": 4,
        "saida_descoberta": "dados/descobertas/ats_teste.json",
        "relatorio": {"vagas_minimas": 1, "completude_minima": 0.5},
    },
    "fontes": {
        "workable": {
            "tipo": "api_publica_por_empresa",
            "dominios": ["apply.workable.com"],
            "verificar_robots": True,
            "ativa": True,
            "termos": TERMOS_OK,
            "endpoint": "https://apply.workable.com/api/v1/widget/accounts/{identificador}?details=true",
        },
        "smartrecruiters": {
            "tipo": "api_publica_por_empresa",
            "dominios": ["api.smartrecruiters.com"],
            "verificar_robots": True,
            "ativa": True,
            "termos": TERMOS_OK,
            "endpoint": "https://api.smartrecruiters.com/v1/companies/{identificador}/postings",
            "url_vaga": "https://jobs.smartrecruiters.com/{identificador}/{id}",
            "paises_iso": {"br": "BR", "us": "US"},
        },
        "personio": {
            "tipo": "api_publica_por_empresa",
            "dominios": ["jobs.personio.de"],
            "verificar_robots": True,
            "ativa": True,
            "termos": TERMOS_OK,
            "endpoint": "https://{identificador}.jobs.personio.de/xml",
            "url_vaga": "https://{identificador}.jobs.personio.de/job/{id}",
        },
    },
    "empresas_alvo": [
        {
            "nome": "Acme Ficticia",
            "ats": {"workable": "acme", "smartrecruiters": "AcmeSR", "personio": "acme"},
        },
        {"nome": "Beta Dados", "ats": {}},
    ],
}

ROBOTS_LIVRE = "User-agent: *\nAllow: /\n"

WORKABLE = {
    "name": "Acme Ficticia",
    "jobs": [
        {
            "title": "Estagio em Dados",
            "shortcode": "AB12",
            "url": "https://apply.workable.com/j/AB12",
            "country": "Brazil",
            "city": "Sao Paulo",
            "telecommuting": False,
            "employment_type": "Full-time",
            "published_on": "2026-10-30",
            "description": "<p>Apoie o time de dados com SQL e Python em projetos de analise. "
            "Voce estuda ciencia da computacao ou areas afins e quer aprender no dia a dia.</p>",
        },
        {"title": "", "shortcode": "ZZ", "url": "https://apply.workable.com/j/ZZ"},
    ],
}

SMARTRECRUITERS = {
    "totalFound": 2,
    "content": [
        {
            "id": "7440001",
            "name": "Junior Backend Developer",
            "releasedDate": "2026-10-28T12:00:00.000Z",
            "location": {"city": "Curitiba", "country": "br", "remote": True, "hybrid": False},
            "experienceLevel": {"id": "entry_level", "label": "Entry Level"},
            "company": {"identifier": "AcmeSR", "name": "Acme Ficticia"},
        },
        {
            "id": "7440002",
            "name": "Intern Data",
            "location": {"city": "Recife", "country": "br"},
            "experienceLevel": {"id": "internship", "label": "Internship"},
            "company": {"identifier": "AcmeSR", "name": "Acme Ficticia"},
        },
    ],
}

PERSONIO = """<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
  <position>
    <id>991</id>
    <office>Sao Paulo, Brazil</office>
    <name>Working Student Engenharia</name>
    <jobDescriptions>
      <jobDescription>
        <name>Tarefas</name>
        <value><![CDATA[<p>Escrever testes e ajudar no deploy do time de plataforma.</p>]]></value>
      </jobDescription>
    </jobDescriptions>
    <seniority>student</seniority>
    <createdAt>2026-10-20T09:00:00+00:00</createdAt>
  </position>
</workzag-jobs>"""


def configuracao(**alteracoes) -> dict:
    config = copy.deepcopy(CONFIG_BASE)
    for chave, valor in alteracoes.items():
        config[chave] = valor
    return config


def aplicar(monkeypatch, config: dict) -> None:
    def carregar(nome: str) -> dict:
        return config if nome == "fontes" else carregar_real(nome)

    for modulo in (conformidade, base, ats, descoberta, rodada):
        monkeypatch.setattr(modulo, "carregar", carregar, raising=False)


def cliente() -> httpx.Client:
    return httpx.Client()


def sem_espera(monkeypatch) -> None:
    real = base.ambiente()
    monkeypatch.setattr(base, "ambiente", lambda: replace(real, rate_limit_rps=0))
    monkeypatch.setattr(base.ColetorHttp, "_dormir", lambda self, segundos: None)
