from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from pypdf import PageObject
from pypdf.errors import PyPdfError

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.paginas import ler_pdf

IDENTIDADE = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
MILESIMO = 1000.0


class PdfIlegivel(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Fragmento:
    texto: str
    y: float
    pagina: int


@dataclass(frozen=True, slots=True)
class Caixa:
    x0: float
    x1: float
    y0: float
    y1: float
    y_linha: float
    pagina: int


@dataclass(frozen=True, slots=True)
class Fonte:
    primeiro: int
    larguras: tuple[float, ...]
    faltante: float | None


@dataclass(frozen=True, slots=True)
class Leitura:
    fragmentos: tuple[Fragmento, ...]
    caixas: tuple[Caixa, ...]


def _produto(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return (
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    )


def _numeros(valores: list, total: int) -> list[float]:
    achados = [float(v) for v in valores[:total]]
    if len(achados) != total:
        raise PdfIlegivel("operador de texto sem operandos")
    return achados


def _fonte_do_recurso(recurso, config: ConfiguracaoValidador) -> Fonte:
    recurso = recurso.get_object() if recurso is not None else {}
    larguras = recurso.get("/Widths")
    if larguras is None:
        return Fonte(0, (), config.layout.pdf.largura_sem_metrica_em * MILESIMO)
    descritor = recurso.get("/FontDescriptor")
    faltante = descritor.get_object().get("/MissingWidth") if descritor is not None else None
    return Fonte(
        int(recurso.get("/FirstChar", 0)),
        tuple(float(w) for w in larguras.get_object()),
        float(faltante) if faltante is not None else 0.0,
    )


class Medidor:
    def __init__(self, pagina: PageObject, indice: int, config: ConfiguracaoValidador) -> None:
        recursos = pagina.get("/Resources")
        fontes = recursos.get_object().get("/Font") if recursos is not None else None
        self.fontes = fontes.get_object() if fontes is not None else {}
        self.indice = indice
        self.config = config
        self.cache: dict[str, Fonte] = {}
        self.fonte = Fonte(0, (), config.layout.pdf.largura_sem_metrica_em * MILESIMO)
        self.tamanho = 0.0
        self.entrelinha = 0.0
        self.tm = IDENTIDADE
        self.tlm = IDENTIDADE
        self.caixas: list[Caixa] = []
        self.fragmentos: list[Fragmento] = []

    def texto(self, texto: str, cm: list[float], tm: list[float], _fonte, _tamanho) -> None:
        if not texto.strip():
            return
        y = tm[4] * cm[2] + tm[5] * cm[3] + cm[5]
        self.fragmentos.append(Fragmento(texto, y, self.indice))

    def antes(self, operador: bytes, operandos: list, cm: list[float], _tm) -> None:
        nome = operador.decode("latin-1")
        if nome == "BT":
            self.tm = self.tlm = IDENTIDADE
        elif nome == "Tm":
            self.tm = self.tlm = tuple(_numeros(operandos, 6))
        elif nome in ("Td", "TD"):
            tx, ty = _numeros(operandos, 2)
            if nome == "TD":
                self.entrelinha = -ty
            self._mover(tx, ty)
        elif nome == "T*":
            self._mover(0.0, -self.entrelinha)
        elif nome == "TL":
            self.entrelinha = _numeros(operandos, 1)[0]
        elif nome == "Tf":
            self._trocar_fonte(str(operandos[0]), _numeros(operandos[1:], 1)[0])
        elif nome in ("Tj", "TJ", "'", '"'):
            if nome in ("'", '"'):
                self._mover(0.0, -self.entrelinha)
            self._mostrar(operandos[-1], cm)

    def _mover(self, tx: float, ty: float) -> None:
        self.tlm = _produto((1.0, 0.0, 0.0, 1.0, tx, ty), self.tlm)
        self.tm = self.tlm

    def _trocar_fonte(self, nome: str, tamanho: float) -> None:
        self.tamanho = tamanho
        if nome not in self.cache:
            self.cache[nome] = _fonte_do_recurso(self.fontes.get(nome), self.config)
        self.fonte = self.cache[nome]

    def _largura(self, trecho: bytes) -> float:
        total = 0.0
        for codigo in trecho:
            posicao = codigo - self.fonte.primeiro
            if 0 <= posicao < len(self.fonte.larguras):
                total += self.fonte.larguras[posicao]
            elif self.fonte.faltante is not None:
                total += self.fonte.faltante
        return total

    def _mostrar(self, operando, cm: list[float]) -> None:
        itens = operando if isinstance(operando, list) else [operando]
        cursor = 0.0
        inicio: float | None = None
        fim = 0.0
        for item in itens:
            if isinstance(item, (int, float)):
                cursor -= float(item)
                continue
            bruto = bytes(getattr(item, "original_bytes", item))
            largura = self._largura(bruto)
            if largura > 0:
                inicio = cursor if inicio is None else inicio
                fim = cursor + largura
            cursor += largura
        if inicio is not None and self.tamanho > 0:
            self._registrar(inicio, fim, cm)
        self.tm = _produto((1.0, 0.0, 0.0, 1.0, cursor * self.tamanho / MILESIMO, 0.0), self.tm)

    def _registrar(self, inicio: float, fim: float, cm: list[float]) -> None:
        pdf = self.config.layout.pdf
        m = _produto(self.tm, tuple(cm))
        escala_x = math.hypot(m[0], m[1])
        escala_y = math.hypot(m[2], m[3])
        x0 = m[4] + inicio * self.tamanho / MILESIMO * escala_x
        x1 = m[4] + fim * self.tamanho / MILESIMO * escala_x
        corpo = self.tamanho * escala_y
        self.caixas.append(
            Caixa(
                x0,
                x1,
                m[5] - pdf.descendente_em * corpo,
                m[5] + pdf.ascendente_em * corpo,
                m[5],
                self.indice,
            )
        )


def ler_geometria(pdf: Path, config: ConfiguracaoValidador) -> Leitura:
    leitor = ler_pdf(pdf)
    if leitor is None:
        raise PdfIlegivel("pdf ilegivel")
    fragmentos: list[Fragmento] = []
    caixas: list[Caixa] = []
    try:
        for indice, pagina in enumerate(leitor.pages, start=1):
            medidor = Medidor(pagina, indice, config)
            pagina.extract_text(visitor_operand_before=medidor.antes, visitor_text=medidor.texto)
            fragmentos += medidor.fragmentos
            caixas += medidor.caixas
    except (PyPdfError, ValueError, KeyError, TypeError, IndexError, AttributeError) as erro:
        raise PdfIlegivel("pdf com conteudo ilegivel") from erro
    return Leitura(tuple(fragmentos), tuple(caixas))
