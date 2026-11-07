from __future__ import annotations

from datetime import date

from src.coletor.contratos import ModeloTrabalho
from src.triagem.configuracao import Filtros
from src.triagem.contratos import Motivo, VagaTriagem
from src.triagem.normalizacao import normalizar
from src.triagem.regra import extrair_anos_experiencia, inferir_funcao

MODELOS_COM_LOCAL = frozenset({ModeloTrabalho.PRESENCIAL, ModeloTrabalho.HIBRIDO})


def _contem_palavra(texto_normalizado: str, termo: str) -> bool:
    return f" {normalizar(termo)} " in f" {texto_normalizado} "


def _funcao(vaga: VagaTriagem, filtros: Filtros) -> tuple[Motivo, str] | None:
    funcao = inferir_funcao(vaga.titulo, vaga.descricao)
    if funcao not in filtros.eliminatorios.funcoes_aceitas:
        return Motivo.FUNCAO, funcao.value
    return None


def _senioridade(vaga: VagaTriagem, filtros: Filtros) -> tuple[Motivo, str] | None:
    if vaga.senioridade in filtros.senioridades_recusadas:
        return Motivo.SENIORIDADE, vaga.senioridade.value
    return None


def _titulo(vaga: VagaTriagem, filtros: Filtros) -> tuple[Motivo, str] | None:
    titulo = normalizar(vaga.titulo)
    for termo in filtros.eliminatorios.recusa_titulos_com:
        if _contem_palavra(titulo, termo):
            return Motivo.TITULO, termo
    return None


def _anos(vaga: VagaTriagem, filtros: Filtros) -> tuple[Motivo, str] | None:
    anos = extrair_anos_experiencia(vaga.descricao)
    if anos is not None and anos > filtros.eliminatorios.exige_anos_experiencia_max:
        return Motivo.ANOS, str(anos)
    return None


def _modelo(vaga: VagaTriagem, filtros: Filtros) -> tuple[Motivo, str] | None:
    if vaga.modelo not in filtros.modelos_aceitos:
        return Motivo.MODELO, vaga.modelo.value
    return None


def _pais(vaga: VagaTriagem, filtros: Filtros) -> tuple[Motivo, str] | None:
    if vaga.pais and vaga.pais not in filtros.paises_aceitos:
        return Motivo.PAIS, vaga.pais
    return None


def _local(vaga: VagaTriagem, filtros: Filtros) -> tuple[Motivo, str] | None:
    if vaga.modelo not in MODELOS_COM_LOCAL or not vaga.local.strip():
        return None
    local = normalizar(vaga.local)
    regioes = filtros.eliminatorios.recusa_se_exige_presencial_fora_de
    if any(_contem_palavra(local, regiao) for regiao in regioes):
        return None
    return Motivo.LOCAL, vaga.modelo.value


def _idade(vaga: VagaTriagem, filtros: Filtros, hoje: date) -> tuple[Motivo, str] | None:
    if vaga.publicada_em is None:
        return None
    dias = (hoje - vaga.publicada_em).days
    if dias > filtros.eliminatorios.idade_maxima_dias:
        return Motivo.IDADE, str(dias)
    return None


def motivo_de_descarte(
    vaga: VagaTriagem, filtros: Filtros, hoje: date
) -> tuple[Motivo, str] | None:
    for regra in (_funcao, _senioridade, _titulo, _anos, _modelo, _pais, _local):
        achado = regra(vaga, filtros)
        if achado is not None:
            return achado
    return _idade(vaga, filtros, hoje)
