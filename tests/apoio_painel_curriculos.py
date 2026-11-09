from __future__ import annotations

import json
from pathlib import Path

from src.config import carregar
from src.gerador.configuracao import configuracao_gerador

GERADOR = configuracao_gerador()
ARQUIVOS = GERADOR.laco.arquivos
PDF_BYTES = b"%PDF-1.4\n% conteudo ficticio de teste\n"
SLOTS_BASE = {
    "sobre": {"texto": "Texto do sobre da familia.", "techs": ["Python"]},
    "projetos": [
        {"bloco": "proj_alfa", "bullets": [{"id": "b1", "texto": "Fez a API.", "techs": []}]}
    ],
}


def violacao(
    nivel: str, codigo: str = "V10", regra: str = "tecnologia", detalhe: str = "detalhe"
) -> dict:
    return {
        "codigo": codigo,
        "regra": regra,
        "nivel": nivel,
        "detalhe": detalhe,
        "trecho": "trecho do curriculo",
        "sugestao": "sugestao curta",
    }


def gravar_json(caminho: Path, dados: object) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding="utf-8")


def pasta_da_vaga(dados: Path, vaga: str) -> Path:
    return dados / GERADOR.laco.pasta_vagas / vaga


def pasta_da_familia(dados: Path, nome: str) -> Path:
    return dados / carregar("painel")["curriculos"]["pasta_familias"] / nome


def gravar_versao(
    pasta: Path,
    *,
    familia: str = "backend_arquitetura",
    idioma: str = "pt",
    violacoes: list[dict] | None = (),
    pdf: bool = True,
    slots: dict | None = None,
    custos: tuple[str, ...] = ("0.0100",),
    anterior: dict | None = None,
    publicada: bool = True,
) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    pasta_tentativas = pasta / GERADOR.laco.pasta_tentativas
    for numero, custo in enumerate(custos, start=1):
        gravar_json(
            pasta_tentativas / str(numero) / ARQUIVOS.meta,
            {"tentativa": numero, "custo_usd": custo, "familia": familia, "idioma": idioma},
        )
        gravar_json(pasta_tentativas / str(numero) / ARQUIVOS.slots, slots or SLOTS_BASE)
    if not publicada:
        return
    ultima = len(custos)
    gravar_json(
        pasta / ARQUIVOS.historico,
        {
            "versoes": [
                {
                    "versao": 1,
                    "tentativa": ultima,
                    "criada_em": "2026-11-05T12:30:00+00:00",
                    "pdf_sha256": "a" * 64,
                    "familia": familia,
                    "idioma": idioma,
                    "motivo": None,
                }
            ],
            "refacoes": [],
        },
    )
    if violacoes is not None:
        gravar_json(pasta / ARQUIVOS.validacao, list(violacoes))
    if pdf:
        (pasta / f"{GERADOR.compilacao.nome_arquivo}.pdf").write_bytes(PDF_BYTES)
    gravar_json(
        pasta / ARQUIVOS.diff,
        {
            "versao": 1,
            "tentativa": ultima,
            "tentativa_anterior": 1 if anterior else None,
            "slots": anterior or {},
            "corte": [],
        },
    )
