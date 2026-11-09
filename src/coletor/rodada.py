from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from src.coletor import personio, smartrecruiters, workable  # noqa: F401
from src.coletor.base import registro
from src.coletor.conformidade import TermosNaoPermitem, exigir_termos_permitidos
from src.coletor.contratos import ResultadoColeta
from src.config import carregar


@dataclass(slots=True)
class RelatorioFonte:
    fonte: str
    ligada: bool
    vagas: int = 0
    unicas: int = 0
    completude: float = 0.0
    erros: list[str] = field(default_factory=list)
    rende: bool = False


def _erros(resultado: ResultadoColeta) -> list[str]:
    erros = [resultado.erro] if resultado.erro else []
    erros += [f"{ident}: {msg}" for ident, msg in (resultado.evidencia.get("falhas") or {}).items()]
    erros += [m.value for m in resultado.motivos if not erros]
    return erros


def rodar_fontes(cliente: httpx.Client | None = None, limite: int = 50) -> list[RelatorioFonte]:
    config = carregar("fontes")["ats"]
    minimo = config["relatorio"]
    relatorios = []
    for slug in config["fontes"]:
        try:
            exigir_termos_permitidos(slug)
        except TermosNaoPermitem as exc:
            relatorios.append(RelatorioFonte(fonte=slug, ligada=False, erros=[str(exc)]))
            continue
        coletor = registro()[slug](client=cliente)
        resultado = coletor.coletar(limite)
        coletor.fechar()
        completude = round(resultado.completude_media, 2)
        relatorios.append(
            RelatorioFonte(
                fonte=slug,
                ligada=True,
                vagas=len(resultado.vagas),
                unicas=resultado.unicas,
                completude=completude,
                erros=_erros(resultado),
                rende=len(resultado.vagas) >= int(minimo["vagas_minimas"])
                and completude >= float(minimo["completude_minima"]),
            )
        )
    return relatorios


def formatar(relatorios: list[RelatorioFonte]) -> str:
    linhas = []
    for r in relatorios:
        estado = "ligada" if r.ligada else "desligada"
        corte = "" if r.rende or not r.ligada else " corte_sugerido"
        erros = "; ".join(r.erros) or "-"
        linhas.append(
            f"{r.fonte} {estado} vagas={r.vagas} unicas={r.unicas} "
            f"completude={r.completude:.2f}{corte} erros={erros}"
        )
    return "\n".join(linhas)


if __name__ == "__main__":
    print(formatar(rodar_fontes()))
