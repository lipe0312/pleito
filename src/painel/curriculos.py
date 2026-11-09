from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Protocol

from src.config import ambiente, carregar
from src.gerador.configuracao import ConfiguracaoGerador, configuracao_gerador

TIPO_FAMILIA = "familia"
TIPO_VAGA = "vaga"
BASE_FAMILIA = "familia"
BASE_ANTERIOR = "anterior"
BASE_NENHUMA = "nenhuma"
SITUACAO_FUNCIONAL = "funcional"


@dataclass(frozen=True, slots=True)
class Violacao:
    codigo: str
    regra: str
    nivel: str
    detalhe: str
    trecho: str
    sugestao: str


@dataclass(frozen=True, slots=True)
class VersaoPublicada:
    versao: int
    tentativa: int
    familia: str
    idioma: str
    criada_em: datetime | None
    motivo: str | None


@dataclass(frozen=True, slots=True)
class LinhaDeDiff:
    nome: str
    saiu: tuple[str, ...]
    entrou: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Curriculo:
    tipo: str
    id: str
    titulo: str
    versoes: tuple[VersaoPublicada, ...]
    violacoes: tuple[Violacao, ...] | None
    tentativas: int
    custo_usd: Decimal
    tem_pdf: bool
    projetos: tuple[str, ...]
    base_tipo: str
    base_rotulo: str
    diff: tuple[LinhaDeDiff, ...]

    @property
    def situacao(self) -> str:
        return situacao_de(bool(self.versoes), self.tem_pdf, self.violacoes)

    @property
    def funcional(self) -> bool:
        return self.situacao == SITUACAO_FUNCIONAL


class RepositorioCurriculos(Protocol):
    def curriculos(self) -> list[Curriculo]: ...

    def pdf(self, tipo: str, ident: str) -> bytes | None: ...


def situacao_de(publicada: bool, tem_pdf: bool, violacoes: tuple[Violacao, ...] | None) -> str:
    if not publicada:
        return "sem_versao"
    if violacoes is None:
        return "sem_validacao"
    negam = set(carregar("painel")["curriculos"]["niveis_que_negam_selo"])
    if any(violacao.nivel in negam for violacao in violacoes):
        return "com_bloqueio"
    return SITUACAO_FUNCIONAL if tem_pdf else "sem_pdf"


def _linhas(valor: object, caminho: tuple[str, ...]) -> Iterator[str]:
    if isinstance(valor, dict):
        for chave, filho in valor.items():
            yield from _linhas(filho, (*caminho, str(chave)))
    elif isinstance(valor, list) and any(isinstance(item, (dict, list)) for item in valor):
        for posicao, filho in enumerate(valor, start=1):
            nome = filho.get("bloco") or filho.get("id") if isinstance(filho, dict) else None
            yield from _linhas(filho, (*caminho, str(nome or posicao)))
    elif isinstance(valor, list):
        yield f"{' / '.join(caminho)}: {', '.join(str(item) for item in valor)}"
    elif valor is not None:
        yield f"{' / '.join(caminho)}: {valor}"


def diferenca_de_linhas(nome: str, antes: object, depois: object) -> LinhaDeDiff | None:
    a = list(_linhas(antes, (nome,)))
    b = list(_linhas(depois, (nome,)))
    saiu: list[str] = []
    entrou: list[str] = []
    for operacao, a1, a2, b1, b2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if operacao != "equal":
            saiu += a[a1:a2]
            entrou += b[b1:b2]
    if not saiu and not entrou:
        return None
    return LinhaDeDiff(nome, tuple(saiu), tuple(entrou))


def diferenca_de_slots(base: dict, atual: dict) -> tuple[LinhaDeDiff, ...]:
    nomes = list(dict.fromkeys([*base, *atual]))
    achados = (diferenca_de_linhas(nome, base.get(nome), atual.get(nome)) for nome in nomes)
    return tuple(linha for linha in achados if linha is not None)


def _momento(texto: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto))
    except ValueError:
        return None


def _decimal(texto: object) -> Decimal:
    try:
        return Decimal(str(texto))
    except InvalidOperation:
        return Decimal(0)


class RepositorioArquivosCurriculos:
    def __init__(self, pasta_dados: Path | None = None) -> None:
        configuracao = carregar("painel")["curriculos"]
        self._gerador: ConfiguracaoGerador = configuracao_gerador()
        self._padrao = re.compile(configuracao["padrao_id"])
        self._json_max = int(configuracao["json_max_bytes"])
        self._pdf_max = int(configuracao["pdf_max_bytes"])
        self._limite = int(configuracao["limite"])
        base = pasta_dados if pasta_dados is not None else ambiente().dados
        self._raizes = {
            TIPO_FAMILIA: base / str(configuracao["pasta_familias"]),
            TIPO_VAGA: base / self._gerador.laco.pasta_vagas,
        }

    def _pastas(self, tipo: str) -> dict[str, Path]:
        raiz = self._raizes[tipo]
        if not raiz.is_dir():
            return {}
        achadas = (
            pasta
            for pasta in raiz.iterdir()
            if self._padrao.fullmatch(pasta.name) and pasta.is_dir() and not pasta.is_symlink()
        )
        return {pasta.name: pasta for pasta in sorted(achadas, key=lambda p: (len(p.name), p.name))}

    def _json(self, caminho: Path) -> object | None:
        if not caminho.is_file() or caminho.is_symlink():
            return None
        if caminho.stat().st_size > self._json_max:
            raise ValueError(f"arquivo grande demais: {caminho.name}")
        return json.loads(caminho.read_text(encoding="utf-8"))

    def _objeto(self, caminho: Path) -> dict:
        lido = self._json(caminho)
        if lido is None:
            return {}
        if not isinstance(lido, dict):
            raise ValueError(f"formato inesperado: {caminho.name}")
        return lido

    def _caminho_do_pdf(self, pasta: Path) -> Path:
        return pasta / f"{self._gerador.compilacao.nome_arquivo}.pdf"

    def _tem_pdf(self, pasta: Path) -> bool:
        caminho = self._caminho_do_pdf(pasta)
        return caminho.is_file() and not caminho.is_symlink() and (
            caminho.stat().st_size <= self._pdf_max
        )

    def _versoes(self, pasta: Path) -> tuple[VersaoPublicada, ...]:
        historico = self._objeto(pasta / self._gerador.laco.arquivos.historico)
        try:
            return tuple(
                VersaoPublicada(
                    versao=int(bruta["versao"]),
                    tentativa=int(bruta["tentativa"]),
                    familia=str(bruta.get("familia", "")),
                    idioma=str(bruta.get("idioma", "")),
                    criada_em=_momento(bruta.get("criada_em")),
                    motivo=bruta.get("motivo") or None,
                )
                for bruta in historico.get("versoes", [])
            )
        except (KeyError, TypeError, AttributeError) as erro:
            raise ValueError("historico fora do formato") from erro

    def _violacoes(self, pasta: Path) -> tuple[Violacao, ...] | None:
        lido = self._json(pasta / self._gerador.laco.arquivos.validacao)
        if lido is None:
            return None
        if not isinstance(lido, list):
            raise ValueError("validacao fora do formato")
        return tuple(
            Violacao(
                codigo=str(bruta.get("codigo", "")),
                regra=str(bruta.get("regra", "")),
                nivel=str(bruta.get("nivel", "")),
                detalhe=str(bruta.get("detalhe", "")),
                trecho=str(bruta.get("trecho", "")),
                sugestao=str(bruta.get("sugestao", "")),
            )
            for bruta in lido
        )

    def _tentativas(self, pasta: Path) -> list[Path]:
        raiz = pasta / self._gerador.laco.pasta_tentativas
        if not raiz.is_dir():
            return []
        numeradas = [p for p in raiz.iterdir() if p.is_dir() and re.fullmatch("[0-9]+", p.name)]
        return sorted(numeradas, key=lambda p: int(p.name))

    def _custo(self, tentativas: list[Path]) -> Decimal:
        meta = self._gerador.laco.arquivos.meta
        return sum(
            (_decimal(self._objeto(t / meta).get("custo_usd", "0")) for t in tentativas),
            Decimal(0),
        )

    def _slots(self, pasta: Path, versoes: tuple[VersaoPublicada, ...]) -> dict:
        if not versoes:
            return {}
        arquivos = self._gerador.laco
        return self._objeto(
            pasta / arquivos.pasta_tentativas / str(versoes[-1].tentativa) / arquivos.arquivos.slots
        )

    def _base_da_familia(self, versoes: tuple[VersaoPublicada, ...]) -> tuple[str, dict] | None:
        if not versoes:
            return None
        alvo = (versoes[-1].familia, versoes[-1].idioma)
        for pasta in self._pastas(TIPO_FAMILIA).values():
            publicadas = self._versoes(pasta)
            if publicadas and (publicadas[-1].familia, publicadas[-1].idioma) == alvo:
                return f"{alvo[0]} ({alvo[1]})", self._slots(pasta, publicadas)
        return None

    def _diff(self, tipo: str, pasta: Path, versoes, slots: dict) -> tuple[str, str, tuple]:
        base = self._base_da_familia(versoes) if tipo == TIPO_VAGA else None
        if base is not None:
            rotulo, slots_da_base = base
            return BASE_FAMILIA, rotulo, diferenca_de_slots(slots_da_base, slots)
        diff = self._objeto(pasta / self._gerador.laco.arquivos.diff)
        if diff.get("tentativa_anterior") is None:
            return BASE_NENHUMA, "", ()
        linhas = (
            diferenca_de_linhas(nome, par.get("antes"), par.get("depois"))
            for nome, par in diff.get("slots", {}).items()
        )
        return BASE_ANTERIOR, "", tuple(linha for linha in linhas if linha is not None)

    def _montar(self, tipo: str, ident: str, pasta: Path) -> Curriculo:
        versoes = self._versoes(pasta)
        slots = self._slots(pasta, versoes)
        tentativas = self._tentativas(pasta)
        base_tipo, base_rotulo, diff = self._diff(tipo, pasta, versoes, slots)
        if tipo == TIPO_FAMILIA and versoes:
            titulo = f"{versoes[-1].familia} ({versoes[-1].idioma})"
        elif tipo == TIPO_FAMILIA:
            titulo = ident
        else:
            titulo = carregar("painel")["curriculos"]["rotulo_vaga"].format(id=ident)
        return Curriculo(
            tipo=tipo,
            id=ident,
            titulo=titulo,
            versoes=versoes,
            violacoes=self._violacoes(pasta),
            tentativas=len(tentativas),
            custo_usd=self._custo(tentativas),
            tem_pdf=self._tem_pdf(pasta),
            projetos=tuple(
                str(entrada["bloco"])
                for entrada in slots.get("projetos", [])
                if isinstance(entrada, dict) and "bloco" in entrada
            ),
            base_tipo=base_tipo,
            base_rotulo=base_rotulo,
            diff=diff,
        )

    def curriculos(self) -> list[Curriculo]:
        familias = [
            self._montar(TIPO_FAMILIA, ident, pasta)
            for ident, pasta in self._pastas(TIPO_FAMILIA).items()
        ]
        vagas = [
            self._montar(TIPO_VAGA, ident, pasta)
            for ident, pasta in reversed(self._pastas(TIPO_VAGA).items())
        ]
        return [*familias, *vagas[: self._limite]]

    def pdf(self, tipo: str, ident: str) -> bytes | None:
        if tipo not in self._raizes:
            return None
        pasta = self._pastas(tipo).get(ident)
        if pasta is None or not self._tem_pdf(pasta):
            return None
        return self._caminho_do_pdf(pasta).read_bytes()
