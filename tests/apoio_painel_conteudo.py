from __future__ import annotations

from pathlib import Path

import yaml

from src.config import carregar
from src.conteudo.arquivo import destino_conteudo
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.sincronizacao import configuracao_sincronizacao

CONTEUDO = configuracao_conteudo()
SINCRONIZACAO = configuracao_sincronizacao()
IDIOMAS = ["pt", "en"]


def pasta_conteudo(dados: Path) -> Path:
    destino = destino_conteudo(dados, CONTEUDO)
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def gravar_yaml(caminho: Path, dados: dict) -> None:
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")


def bloco_projeto(ident: str, nome: str, link: str, descricao: str = "Descricao ficticia.") -> dict:
    return {
        "id": ident,
        "tipo": "projeto",
        "imutavel": {
            "nome": {i: nome for i in IDIOMAS},
            "descricao": {i: descricao for i in IDIOMAS},
            "link": {i: link for i in IDIOMAS},
        },
        "techs": ["Python"],
    }


def gravar_blocos(dados: Path, blocos: list[dict]) -> None:
    gravar_yaml(
        pasta_conteudo(dados) / CONTEUDO.arquivo_blocos, {"idiomas": IDIOMAS, "blocos": blocos}
    )


def gravar_inventario(dados: Path, techs: list[dict]) -> None:
    gravar_yaml(pasta_conteudo(dados) / CONTEUDO.arquivo_inventario, {"techs": techs})


def sugestao(
    ident: str,
    *,
    tipo: str = "projeto_novo",
    nome: str = "Projeto Novo",
    projeto_id: str = "proj_novo",
    tech: str | None = None,
    status: str = "pendente",
    origem: str = "github",
) -> dict:
    url = f"{carregar('conteudo')['sincronizacao']['github']['url_publica']}/ficticio/{projeto_id}"
    bruta = {
        "id": ident,
        "tipo": tipo,
        "status": status,
        "origem": origem,
        "projeto": {"id": projeto_id, "nome": nome, "url": url, "descricao": "README ficticio."},
        "evidencias": ["linguagem:Python"],
        "vista_em": "2026-11-05T10:00:00+00:00",
    }
    if tech:
        bruta["tech"] = tech
        bruta["ancora"] = {"tipo": "projeto", "ref": projeto_id, "fonte": url}
    return bruta


def gravar_sugestoes(dados: Path, sugestoes: list[dict]) -> None:
    gravar_yaml(
        pasta_conteudo(dados) / SINCRONIZACAO.arquivo_sugestoes,
        {"geradas_em": "2026-11-05T10:00:00+00:00", "completo": True, "sugestoes": sugestoes},
    )
