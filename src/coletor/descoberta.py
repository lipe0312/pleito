from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import httpx

from src.coletor.ats import ColetorAts, exigir_ats_liberado, identificador_valido
from src.coletor.base import registro
from src.config import RAIZ, carregar


def variantes_do_nome(nome: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    palavras = re.findall(r"[a-z0-9]+", sem_acento.lower())
    if not palavras:
        return []
    variantes = ["".join(palavras), "-".join(palavras), palavras[0]]
    return list(dict.fromkeys(variantes))


def candidatos_da_empresa(empresa: dict, maximo: int) -> list[str]:
    explicitos = [str(c) for c in empresa.get("candidatos") or []]
    todos = list(dict.fromkeys(explicitos + variantes_do_nome(empresa["nome"])))
    return [c for c in todos if identificador_valido(c)][:maximo]


def _coletor(slug: str, cliente: httpx.Client | None) -> ColetorAts:
    return registro()[slug](client=cliente)


def descobrir(
    empresas: list[dict], cliente: httpx.Client | None = None, saida: Path | None = None
) -> list[dict]:
    config = carregar("fontes")["ats"]
    sugestoes: list[dict] = []
    erros: list[dict] = []
    for slug in config["fontes"]:
        if not exigir_ats_liberado(slug):
            erros.append({"ats": slug, "erro": "fonte desligada ou sem termos revisados"})
            continue
        coletor = _coletor(slug, cliente)
        for empresa in empresas:
            if (empresa.get("ats") or {}).get(slug):
                continue
            for candidato in candidatos_da_empresa(empresa, int(config["candidatos_max"])):
                consulta = coletor.consultar(candidato)
                if consulta.vagas:
                    sugestoes.append(
                        {
                            "empresa": empresa["nome"],
                            "ats": slug,
                            "identificador": candidato,
                            "vagas": len(consulta.vagas),
                        }
                    )
                    break
                if consulta.erro and consulta.status != 404:
                    erros.append(
                        {
                            "empresa": empresa["nome"],
                            "ats": slug,
                            "identificador": candidato,
                            "erro": consulta.erro,
                        }
                    )
        coletor.fechar()
    destino = saida or RAIZ / config["saida_descoberta"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(
            {
                "geradas_em": datetime.now(UTC).isoformat(timespec="seconds"),
                "sugestoes": sugestoes,
                "erros": erros,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return sugestoes


if __name__ == "__main__":
    for item in descobrir(carregar("fontes").get("empresas_alvo") or []):
        print(f"{item['empresa']}: {item['ats']}={item['identificador']} ({item['vagas']} vagas)")
