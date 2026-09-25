from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from viabilidade.contratos import ResultadoColeta, Veredito

ORDEM = {Veredito.NO_GO: 0, Veredito.NAO_TESTADO: 1, Veredito.GO_COM_RESSALVA: 2, Veredito.GO: 3}
SIMBOLO = {
    Veredito.GO: "GO",
    Veredito.GO_COM_RESSALVA: "GO com ressalva",
    Veredito.NO_GO: "NO-GO",
    Veredito.NAO_TESTADO: "nao testado",
}


@dataclass(slots=True)
class Consolidado:
    ingest: dict[str, Veredito] = field(default_factory=dict)
    egress: dict[str, Veredito] = field(default_factory=dict)
    baseline: dict[str, Veredito] = field(default_factory=dict)
    detalhes: dict[str, dict] = field(default_factory=dict)
    gerado_em: datetime = field(default_factory=lambda: datetime.now(UTC))

    def registrar_coleta(self, resultado: ResultadoColeta) -> None:
        self.ingest[resultado.fonte] = resultado.veredito()
        self.detalhes[f"ingest.{resultado.fonte}"] = {
            "vagas": len(resultado.vagas),
            "unicas": resultado.unicas,
            "completude_media": round(resultado.completude_media, 3),
            "http_status": resultado.http_status,
            "robots_permite": resultado.robots_permite,
            "requer_revisao_tos": resultado.requer_revisao_tos,
            "motivos": [m.value for m in resultado.motivos],
            "erro": resultado.erro,
            "duracao_s": resultado.duracao_s,
            "evidencia": resultado.evidencia,
        }

    @property
    def global_(self) -> Veredito:
        ingest_ok = [v for v in self.ingest.values() if ORDEM[v] >= ORDEM[Veredito.GO_COM_RESSALVA]]
        if not ingest_ok:
            return Veredito.NO_GO
        if not self.egress:
            return Veredito.NAO_TESTADO
        melhor_egress = max(self.egress.values(), key=lambda v: ORDEM[v])
        if ORDEM[melhor_egress] < ORDEM[Veredito.GO_COM_RESSALVA]:
            return Veredito.NO_GO
        if not self.baseline or any(
            ORDEM[v] < ORDEM[Veredito.GO_COM_RESSALVA] for v in self.baseline.values()
        ):
            return Veredito.NO_GO
        piores = [melhor_egress, *self.baseline.values(), max(ingest_ok, key=lambda v: ORDEM[v])]
        return min(piores, key=lambda v: ORDEM[v])

    def como_dict(self) -> dict:
        return {
            "gerado_em": self.gerado_em.isoformat(),
            "veredito_global": self.global_.value,
            "ingest": {k: v.value for k, v in self.ingest.items()},
            "egress": {k: v.value for k, v in self.egress.items()},
            "baseline": {k: v.value for k, v in self.baseline.items()},
            "detalhes": self.detalhes,
        }

    def salvar_json(self, destino: Path) -> Path:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(self.como_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destino

    def markdown(self) -> str:
        linhas = [
            "# Veredito de viabilidade",
            "",
            f"Gerado em {self.gerado_em:%Y-%m-%d %H:%M UTC}.",
            "",
            f"**Veredito global: {SIMBOLO[self.global_]}**",
            "",
            "## Ingest por fonte",
            "",
            "| fonte | veredito | vagas | completude | robots | motivos |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for fonte, veredito in sorted(self.ingest.items()):
            d = self.detalhes.get(f"ingest.{fonte}", {})
            motivos = ", ".join(d.get("motivos", [])) or "-"
            linhas.append(
                f"| {fonte} | {SIMBOLO[veredito]} | {d.get('vagas', 0)} | "
                f"{d.get('completude_media', 0):.0%} | {d.get('robots_permite')} | {motivos} |"
            )
        linhas += ["", "## Egress por plataforma", "", "| plataforma | veredito |", "| --- | --- |"]
        for plataforma, veredito in sorted(self.egress.items()) or []:
            linhas.append(f"| {plataforma} | {SIMBOLO[veredito]} |")
        if not self.egress:
            linhas.append("| - | nao testado |")
        linhas += ["", "## Baseline do curriculo", "", "| idioma | veredito |", "| --- | --- |"]
        for idioma, veredito in sorted(self.baseline.items()):
            linhas.append(f"| {idioma} | {SIMBOLO[veredito]} |")
        if not self.baseline:
            linhas.append("| - | nao testado |")
        linhas.append("")
        return "\n".join(linhas)
