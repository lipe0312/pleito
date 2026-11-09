from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from src.config import carregar
from src.conteudo.modelo import Estrito, Identificador
from src.validador.resultado import REGRAS_DE_SEGURANCA, Nivel, Regra

Simbolo = Annotated[str, StringConstraints(min_length=1, max_length=1)]
Fragmento = Annotated[str, StringConstraints(min_length=1)]


class LatexCorpo(Estrito):
    comandos: list[Identificador]
    ambientes: list[Identificador]
    simbolos: list[Simbolo]


def _padroes_compilam(opcoes: dict[str, list[str]]) -> dict[str, list[str]]:
    for padroes in opcoes.values():
        for padrao in padroes:
            re.compile(padrao)
    return opcoes


OpcoesPermitidas = Annotated[
    dict[Identificador, list[Fragmento]], AfterValidator(_padroes_compilam)
]


class LatexPreambulo(Estrito):
    comandos: list[Identificador]
    classes: OpcoesPermitidas
    pacotes: OpcoesPermitidas
    definiveis: list[Identificador]
    simbolos: list[Simbolo]


class Links(Estrito):
    esquema_seguro: Identificador
    dominios: list[Fragmento] = Field(min_length=1)
    esquemas_sem_dominio: list[Fragmento]


class Medidas(Estrito):
    comandos: dict[Identificador, int]
    minimo_mm: float
    maximo_mm: float = Field(gt=0)
    unidades_mm: dict[Identificador, float]

    @model_validator(mode="after")
    def _faixa_e_comandos_validos(self) -> Medidas:
        if self.minimo_mm > self.maximo_mm:
            raise ValueError("minimo_mm maior que maximo_mm")
        if any(total < 1 for total in self.comandos.values()):
            raise ValueError("comando de medida precisa de ao menos um argumento")
        return self


class ConfiguracaoLatex(Estrito):
    comentario: Simbolo
    ambiente_do_corpo: Identificador
    sequencias_proibidas: list[Fragmento]
    links: Links
    medidas: Medidas
    corpo: LatexCorpo
    preambulo: LatexPreambulo

    @model_validator(mode="after")
    def _ambiente_do_corpo_e_permitido(self) -> ConfiguracaoLatex:
        if self.ambiente_do_corpo not in self.corpo.ambientes:
            raise ValueError("ambiente_do_corpo precisa estar nos ambientes do corpo")
        return self


class Alfabeto(Estrito):
    scripts: list[Annotated[str, StringConstraints(pattern=r"^[A-Z]+$")]] = Field(min_length=1)
    scripts_com_base_ascii: list[Annotated[str, StringConstraints(pattern=r"^[A-Z]+$")]]
    extras: list[Simbolo]


class ConfiguracaoCaracteres(Estrito):
    proibidos: list[Simbolo]
    sequencias_proibidas: list[Fragmento]
    categorias_unicode_proibidas: list[Annotated[str, StringConstraints(pattern=r"^[A-Z][a-z]$")]]
    controles_permitidos: list[Simbolo]
    alfabeto: Alfabeto


def _regexes_compilam(padroes: list[str]) -> list[str]:
    for padrao in padroes:
        try:
            re.compile(padrao)
        except re.error as erro:
            raise ValueError(f"regex invalida: {padrao!r}") from erro
    return padroes


PorIdioma = dict[Identificador, list[Fragmento]]


class PreambuloDoConteudo(Estrito):
    parametros_livres: Annotated[list[Fragmento], AfterValidator(_regexes_compilam)]


class ProjetosDoConteudo(Estrito):
    minimo: int = Field(ge=1)
    maximo: int = Field(ge=1)
    rotulo_final: dict[Identificador, Fragmento] = Field(min_length=1)

    @model_validator(mode="after")
    def _minimo_nao_passa_do_maximo(self) -> ProjetosDoConteudo:
        if self.minimo > self.maximo:
            raise ValueError("minimo de projetos maior que o maximo")
        return self


class CopiaDaVaga(Estrito):
    palavras: int = Field(ge=2)


class EmpresaDaVaga(Estrito):
    tamanho_minimo: int = Field(ge=1)
    sufixos: list[Fragmento]


class Negrito(Estrito):
    comandos: list[Identificador] = Field(min_length=1)


class Escapes(Estrito):
    simbolos: list[Simbolo] = Field(min_length=1)


class IdiomaDoConteudo(Estrito):
    marcadores: PorIdioma = Field(min_length=2)
    nomes: dict[Identificador, Fragmento] = Field(min_length=2)


class SecoesDoIdioma(Estrito):
    sobre: Fragmento
    formacao: Fragmento
    experiencia: Fragmento
    projetos: Fragmento


class ConfiguracaoDoConteudo(Estrito):
    trecho_max_chars: int = Field(gt=0)
    secoes: dict[Identificador, SecoesDoIdioma] = Field(min_length=1)
    preambulo: PreambuloDoConteudo
    projetos: ProjetosDoConteudo
    copia_da_vaga: CopiaDaVaga
    empresa_da_vaga: EmpresaDaVaga
    negrito: Negrito
    escapes: Escapes
    idioma: IdiomaDoConteudo

    @model_validator(mode="after")
    def _mesmos_idiomas_em_tudo(self) -> ConfiguracaoDoConteudo:
        idiomas = set(self.secoes)
        por_idioma = [self.projetos.rotulo_final, self.idioma.marcadores, self.idioma.nomes]
        if any(set(lista) != idiomas for lista in por_idioma):
            raise ValueError("secoes, rotulo_final, marcadores e nomes precisam dos mesmos idiomas")
        return self


class LayoutDoLog(Estrito):
    tamanho_max_bytes: int = Field(gt=0)
    erros_max: int = Field(ge=1)
    linhas_do_erro: int = Field(ge=1)
    caixas_max: int = Field(ge=1)
    linhas_da_caixa: int = Field(ge=1)
    defasagem_max_s: float = Field(ge=0)
    overfull_max_pt: float = Field(ge=0)
    underfull_badness_max: int = Field(ge=0)
    overfull_vbox_max_pt: float = Field(ge=0)
    underfull_vbox_badness_max: int = Field(ge=0)


class LayoutDoPdf(Estrito):
    tolerancia_de_linha_pt: float = Field(ge=0)
    ascendente_em: float = Field(gt=0)
    descendente_em: float = Field(ge=0)
    sobreposicao_x_min_pt: float = Field(ge=0)
    sobreposicao_y_min_pt: float = Field(ge=0)
    sobreposicoes_max: int = Field(ge=1)
    largura_sem_metrica_em: float = Field(gt=0)
    caixas_max: int = Field(ge=1)


class LimitesDeLayout(Estrito):
    fonte_min_pt: float = Field(gt=0)
    linespread_min: float = Field(gt=0)
    margem_min_mm: float = Field(ge=0)


class ConfiguracaoDeLayout(Estrito):
    fonte_padrao_pt: float = Field(gt=0)
    chaves_de_margem: list[Identificador] = Field(min_length=1)
    log: LayoutDoLog
    pdf: LayoutDoPdf
    por_idioma: dict[Identificador, LimitesDeLayout] = Field(min_length=1)


Forca = Literal["forte", "fraca"]


class ConfiguracaoDeTecnologias(Estrito):
    palavras_comuns: list[Fragmento]
    evidencias_mostradas: int = Field(ge=1)
    forca_por_origem: dict[Identificador, Forca] = Field(min_length=1)
    forca_padrao: Forca


class ArquivosDeDados(Estrito):
    tecnologias: Fragmento
    vocabulario: Fragmento

    @model_validator(mode="after")
    def _nomes_simples(self) -> ArquivosDeDados:
        for nome in (self.tecnologias, self.vocabulario):
            if Path(nome).name != nome:
                raise ValueError(f"nome de arquivo invalido: {nome!r}")
        if self.tecnologias == self.vocabulario:
            raise ValueError("banco de tecnologias e vocabulario precisam de arquivos diferentes")
        return self


class ExtracaoDoVocabulario(Estrito):
    ngrama_max: int = Field(ge=2)
    sigla_min_chars: int = Field(ge=2)
    termo_min_chars: int = Field(ge=1)


class DadosDoCurriculo(Estrito):
    arquivos: ArquivosDeDados
    vocabulario: ExtracaoDoVocabulario


FonteDeInjecao = Literal[
    "proibidos_tecnologia", "proibidos_numero", "proibidos_palavra", "empresa", "anuncio"
]


class Injecao(Estrito):
    fonte: FonteDeInjecao
    modelo: dict[Identificador, Fragmento] = Field(min_length=1)
    tipos: list[Identificador] = []
    ignorar: list[Fragmento] = []

    @model_validator(mode="after")
    def _modelo_tem_o_termo(self) -> Injecao:
        if any("{termo}" not in texto for texto in self.modelo.values()):
            raise ValueError("modelo de injecao precisa de {termo}")
        return self


class MetasDaRegra(Estrito):
    falso_positivo_max: float = Field(ge=0, le=1)
    falso_negativo_max: float = Field(ge=0, le=1)


class Calibracao(Estrito):
    subpasta: Fragmento
    palavras_extras_do_anuncio: int = Field(ge=0)
    caracteres_fora_do_texto: Annotated[
        Fragmento, AfterValidator(lambda p: _regexes_compilam([p])[0])
    ]
    metas: MetasDaRegra
    por_regra: dict[Regra, MetasDaRegra] = {}
    injecoes: dict[Regra, Injecao]


def _regras_do_nivel(niveis: dict[Regra, Nivel]) -> dict[Regra, Nivel]:
    faltando = sorted(r.value for r in set(Regra) - set(niveis))
    if faltando:
        raise ValueError(f"regra sem nivel: {faltando}")
    rebaixadas = sorted(r.value for r in REGRAS_DE_SEGURANCA if niveis[r] is not Nivel.BLOQUEIA)
    if rebaixadas:
        raise ValueError(f"regra de seguranca precisa ficar em bloqueia: {rebaixadas}")
    return niveis


class ConfiguracaoValidador(Estrito):
    paginas_max: int = Field(gt=0)
    niveis: Annotated[dict[Regra, Nivel], AfterValidator(_regras_do_nivel)]
    latex: ConfiguracaoLatex
    caracteres: ConfiguracaoCaracteres
    tecnologias_conhecidas: list[Fragmento]
    dicionario_tecnologias: list[Fragmento] = []
    tecnologias: ConfiguracaoDeTecnologias
    dados: DadosDoCurriculo
    conteudo: ConfiguracaoDoConteudo
    layout: ConfiguracaoDeLayout
    calibracao: Calibracao

    @model_validator(mode="after")
    def _layout_cobre_os_idiomas_do_conteudo(self) -> ConfiguracaoValidador:
        if set(self.layout.por_idioma) != set(self.conteudo.secoes):
            raise ValueError("layout.por_idioma precisa dos mesmos idiomas das secoes")
        return self


def _achatar(dicionario: dict) -> list[str]:
    return [nome for grupo in dicionario.values() for nome in grupo]


def configuracao_validador(dados: dict | None = None) -> ConfiguracaoValidador:
    bruto = dados if dados is not None else carregar("validador")
    if "dicionario_tecnologias" not in bruto:
        bruto = {**bruto, "dicionario_tecnologias": _achatar(carregar("tecnologias_conhecidas"))}
    return ConfiguracaoValidador.model_validate(bruto)
