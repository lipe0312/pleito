from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml

from src.painel.conteudo import DecisaoRecusada, ProjetoDoBloco, SugestaoPendente
from src.painel.curriculos import (
    BASE_NENHUMA,
    Curriculo,
    LinhaDeDiff,
    VersaoPublicada,
    Violacao,
)
from src.painel.repositorio import _momento


def pdf_ficticio(linhas: list[str]) -> bytes:
    def escapar(texto: str) -> str:
        return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    escritas = " ".join(f"({escapar(linha)}) Tj T*" for linha in linhas)
    fluxo = f"BT /F1 14 Tf 72 760 Td 20 TL {escritas} ET"
    corpos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R"
        " /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(fluxo)} >>\nstream\n{fluxo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = bytearray(b"%PDF-1.4\n")
    posicoes = []
    for numero, corpo in enumerate(corpos, start=1):
        posicoes.append(len(saida))
        saida += f"{numero} 0 obj\n{corpo}\nendobj\n".encode("latin-1", "replace")
    inicio = len(saida)
    saida += f"xref\n0 {len(corpos) + 1}\n0000000000 65535 f \n".encode()
    for posicao in posicoes:
        saida += f"{posicao:010d} 00000 n \n".encode()
    raiz = f"<< /Size {len(corpos) + 1} /Root 1 0 R >>"
    saida += f"trailer\n{raiz}\nstartxref\n{inicio}\n%%EOF\n".encode()
    return bytes(saida)


class CurriculosFicticio:
    def __init__(self, curriculos: list[Curriculo], textos_pdf: dict[tuple[str, str], list[str]]):
        self._curriculos = curriculos
        self._textos_pdf = textos_pdf

    @classmethod
    def de_dados(cls, dados: dict, agora: datetime) -> CurriculosFicticio:
        curriculos = []
        textos = {}
        for bruto in dados.get("curriculos", []):
            violacoes = bruto.get("violacoes")
            curriculo = Curriculo(
                tipo=bruto["tipo"],
                id=str(bruto["id"]),
                titulo=bruto["titulo"],
                versoes=tuple(
                    VersaoPublicada(
                        versao=v["versao"],
                        tentativa=v["tentativa"],
                        familia=v["familia"],
                        idioma=v["idioma"],
                        criada_em=_momento(agora, v.get("dias_atras", 0), v.get("hora", "00:00")),
                        motivo=v.get("motivo"),
                    )
                    for v in bruto.get("versoes", [])
                ),
                violacoes=None if violacoes is None else tuple(Violacao(**v) for v in violacoes),
                tentativas=bruto.get("tentativas", 0),
                custo_usd=Decimal(str(bruto.get("custo_usd", "0"))),
                tem_pdf=bruto.get("tem_pdf", False),
                projetos=tuple(bruto.get("projetos", [])),
                base_tipo=bruto.get("base_tipo", BASE_NENHUMA),
                base_rotulo=bruto.get("base_rotulo", ""),
                diff=tuple(
                    LinhaDeDiff(d["nome"], tuple(d.get("saiu", [])), tuple(d.get("entrou", [])))
                    for d in bruto.get("diff", [])
                ),
            )
            curriculos.append(curriculo)
            textos[(curriculo.tipo, curriculo.id)] = bruto.get("texto_pdf", [curriculo.titulo])
        return cls(curriculos, textos)

    @classmethod
    def de_arquivo(cls, caminho: Path, agora: datetime) -> CurriculosFicticio:
        with Path(caminho).open(encoding="utf-8") as arquivo:
            return cls.de_dados(yaml.safe_load(arquivo) or {}, agora)

    def curriculos(self) -> list[Curriculo]:
        return list(self._curriculos)

    def pdf(self, tipo: str, ident: str) -> bytes | None:
        achado = next((c for c in self._curriculos if (c.tipo, c.id) == (tipo, ident)), None)
        if achado is None or not achado.tem_pdf:
            return None
        return pdf_ficticio(self._textos_pdf[(tipo, ident)])


class ConteudoFicticio:
    def __init__(self, projetos: list[ProjetoDoBloco], sugestoes: list[SugestaoPendente]) -> None:
        self._projetos = projetos
        self._pendentes = {s.id: s for s in sugestoes}
        self.decididas: dict[str, dict] = {}

    @classmethod
    def de_dados(cls, dados: dict) -> ConteudoFicticio:
        projetos = [
            ProjetoDoBloco(
                id=b["id"],
                nome=b["nome"],
                descricao=b.get("descricao", ""),
                link=b.get("link", ""),
                link_clicavel=False,
                origem=b["origem"],
                techs=tuple(b.get("techs", [])),
            )
            for b in dados.get("projetos", [])
        ]
        sugestoes = [
            SugestaoPendente(
                id=b["id"],
                tipo=b["tipo"],
                origem=b["origem"],
                nome=b["nome"],
                url=b["url"],
                descricao=b.get("descricao", ""),
                tech=b.get("tech", ""),
                evidencias=tuple(b.get("evidencias", [])),
            )
            for b in dados.get("sugestoes", [])
        ]
        return cls(projetos, sugestoes)

    @classmethod
    def de_arquivo(cls, caminho: Path) -> ConteudoFicticio:
        with Path(caminho).open(encoding="utf-8") as arquivo:
            return cls.de_dados(yaml.safe_load(arquivo) or {})

    def projetos(self) -> list[ProjetoDoBloco]:
        return list(self._projetos)

    def sugestoes_pendentes(self) -> list[SugestaoPendente]:
        return list(self._pendentes.values())

    def _tirar(self, ident: str) -> None:
        if ident in self.decididas:
            raise DecisaoRecusada("ja_decidida")
        if ident not in self._pendentes:
            raise DecisaoRecusada("inexistente")
        del self._pendentes[ident]

    def aprovar(self, ident: str, por: str, agora: datetime) -> None:
        self._tirar(ident)
        self.decididas[ident] = {"status": "aprovada", "por": por, "em": agora, "motivo": None}

    def rejeitar(self, ident: str, por: str, motivo: str, agora: datetime) -> None:
        if not motivo.strip():
            raise DecisaoRecusada("motivo_vazio")
        self._tirar(ident)
        self.decididas[ident] = {"status": "rejeitada", "por": por, "em": agora, "motivo": motivo}
