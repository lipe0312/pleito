from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import httpx

from src.conteudo.modelo import Inventario
from src.llm.orcamento import OrcamentoEsgotado
from src.llm.roteador import ModeloIndisponivel, Roteador
from src.padroes.configuracao import ConfiguracaoPadroes, configuracao_padroes
from src.triagem.configuracao import ConfiguracaoTriagem, configuracao_triagem
from src.triagem.contratos import (
    Motivo,
    TransicaoRecusada,
    VagaAguardando,
    VagaTriagem,
    texto_do_motivo,
)
from src.triagem.deduplicacao import Deduplicador
from src.triagem.filtros import motivo_de_descarte
from src.triagem.pontuacao import (
    ORIGEM_MODELO,
    PontuacaoAdiada,
    PontuacaoInvalida,
    ResultadoDaPontuacao,
    pontuar_vaga,
)
from src.triagem.pre_nota import calcular_pre_nota


class RepositorioDoFunil(Protocol):
    def pendentes(self) -> list[VagaTriagem]: ...

    def vistas(self) -> list[VagaTriagem]: ...

    def aguardando(self) -> list[VagaAguardando]: ...

    def descartar(self, vaga_id: int, motivo: str, nota: int | None = None) -> None: ...

    def triar(self, vaga_id: int, pre_nota: int) -> None: ...

    def pontuar(self, vaga_id: int, nota: int, registro: dict, origem: str) -> None: ...

    def resultado_em_cache(self, hash_entrada: str) -> dict | None: ...

    def confirmar(self) -> None: ...


@dataclass(slots=True)
class ResumoDoFunil:
    recebidas: int = 0
    duplicadas: int = 0
    descartadas_por_filtro: int = 0
    descartadas_por_pre_nota: int = 0
    triadas: int = 0
    chamadas_ao_modelo: int = 0
    do_cache: int = 0
    invalidas: int = 0
    adiadas: int = 0
    aguardando: int = 0
    transicoes_recusadas: int = 0


def _triar_uma(
    vaga: VagaTriagem,
    original: int | None,
    repositorio: RepositorioDoFunil,
    inventario: Inventario,
    config: ConfiguracaoTriagem,
    hoje: date,
    resumo: ResumoDoFunil,
) -> None:
    if original is not None:
        repositorio.descartar(vaga.id, texto_do_motivo(Motivo.DUPLICATA, f"vaga {original}"))
        resumo.duplicadas += 1
        return
    eliminada = motivo_de_descarte(vaga, config.filtros, hoje)
    if eliminada is not None:
        repositorio.descartar(vaga.id, texto_do_motivo(*eliminada))
        resumo.descartadas_por_filtro += 1
        return
    nota = calcular_pre_nota(vaga, inventario, config, hoje)
    if nota < config.pre_nota_minima:
        repositorio.descartar(vaga.id, texto_do_motivo(Motivo.PRE_NOTA, str(nota)), nota)
        resumo.descartadas_por_pre_nota += 1
        return
    repositorio.triar(vaga.id, nota)
    resumo.triadas += 1


def _triar_novas(
    repositorio: RepositorioDoFunil,
    inventario: Inventario,
    config: ConfiguracaoTriagem,
    hoje: date,
    resumo: ResumoDoFunil,
) -> None:
    deduplicador = Deduplicador(config.normalizacao)
    for vista in repositorio.vistas():
        deduplicador.registrar(vista)
    for vaga in repositorio.pendentes():
        resumo.recebidas += 1
        original = deduplicador.duplicada_de(vaga)
        deduplicador.registrar(vaga)
        try:
            _triar_uma(vaga, original, repositorio, inventario, config, hoje, resumo)
        except TransicaoRecusada:
            resumo.transicoes_recusadas += 1
    repositorio.confirmar()


def _gravar_pontuacao(
    repositorio: RepositorioDoFunil,
    item: VagaAguardando,
    resultado: ResultadoDaPontuacao,
    resumo: ResumoDoFunil,
) -> None:
    repositorio.pontuar(item.vaga.id, resultado.nota, resultado.registro, resultado.origem)
    if resultado.origem == ORIGEM_MODELO:
        resumo.chamadas_ao_modelo += 1
    else:
        resumo.do_cache += 1


def _pontuar_melhores(
    repositorio: RepositorioDoFunil,
    inventario: Inventario,
    roteador: Roteador,
    config: ConfiguracaoTriagem,
    padroes: ConfiguracaoPadroes,
    resumo: ResumoDoFunil,
) -> None:
    ordem = sorted(repositorio.aguardando(), key=lambda item: (-item.pre_nota, item.vaga.id))
    fila = ordem[: config.pre_pontuadas_max]
    for posicao, item in enumerate(fila):
        try:
            try:
                resultado = pontuar_vaga(
                    item.vaga, inventario, roteador, repositorio, config, padroes
                )
            except PontuacaoInvalida as erro:
                resumo.invalidas += 1
                resumo.chamadas_ao_modelo += int(erro.chamou_modelo)
                motivo = texto_do_motivo(Motivo.PONTUACAO_INVALIDA, erro.codigo)
                repositorio.descartar(item.vaga.id, motivo)
            except PontuacaoAdiada:
                resumo.adiadas += 1
            except (ModeloIndisponivel, OrcamentoEsgotado, httpx.HTTPError):
                resumo.adiadas += len(fila) - posicao
                return
            else:
                _gravar_pontuacao(repositorio, item, resultado, resumo)
        except TransicaoRecusada:
            resumo.transicoes_recusadas += 1
        repositorio.confirmar()


def executar_funil(
    repositorio: RepositorioDoFunil,
    inventario: Inventario,
    roteador: Roteador,
    config: ConfiguracaoTriagem | None = None,
    padroes: ConfiguracaoPadroes | None = None,
    hoje: date | None = None,
) -> ResumoDoFunil:
    config = config or configuracao_triagem()
    padroes = padroes or configuracao_padroes()
    resumo = ResumoDoFunil()
    _triar_novas(repositorio, inventario, config, hoje or date.today(), resumo)
    try:
        _pontuar_melhores(repositorio, inventario, roteador, config, padroes, resumo)
    finally:
        resumo.aguardando = len(repositorio.aguardando())
    return resumo
