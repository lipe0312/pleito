from __future__ import annotations

from dataclasses import replace

import pytest

from src.config import carregar
from src.email.eventos import MotivoFila, decidir, politica
from src.email.modelo import Classificacao, Etapa, Motivo

POLITICA = politica()
LIMIAR = POLITICA.limiar
ETAPAS_COM_ESTADO = set(Etapa) - {Etapa.CLASSIFICAR, Etapa.SUSPEITO}


def _reconhecida(etapa: Etapa, confianca: float = LIMIAR) -> Classificacao:
    return Classificacao(etapa, confianca, Motivo.RECONHECIDO, "gupy")


def test_toda_etapa_reconhecivel_tem_estado_de_destino():
    assert set(POLITICA.estado_por_etapa) == ETAPAS_COM_ESTADO


def test_todo_destino_tem_origens_permitidas():
    assert set(POLITICA.origens_permitidas) == set(POLITICA.estado_por_etapa.values())


def test_limiar_vem_do_mesmo_config_do_classificador():
    assert LIMIAR == float(carregar("emails")["limiar_confianca"])


def test_no_limiar_e_autenticado_muda_o_estado():
    decisao = decidir(_reconhecida(Etapa.ENTREVISTA), True, "aplicada_confirmada", POLITICA)
    assert decisao.fila is None
    assert decisao.estado_novo == "entrevista"


def test_abaixo_do_limiar_vai_para_classificar_sem_mudar_estado():
    classificacao = _reconhecida(Etapa.ENTREVISTA, LIMIAR - 0.01)
    decisao = decidir(classificacao, True, "aplicada_confirmada", POLITICA)
    assert decisao.fila is Etapa.CLASSIFICAR
    assert decisao.estado_novo is None
    assert decisao.motivo is MotivoFila.ABAIXO_DO_LIMIAR


def test_classificador_indeciso_vai_para_classificar():
    classificacao = Classificacao(
        Etapa.CLASSIFICAR, 0.95, Motivo.AMBIGUO, "gupy", sugestao=Etapa.TESTE
    )
    decisao = decidir(classificacao, True, "aplicada_confirmada", POLITICA)
    assert decisao.fila is Etapa.CLASSIFICAR
    assert decisao.estado_novo is None
    assert decisao.motivo is MotivoFila.NAO_RECONHECIDO


def test_suspeito_vai_para_a_fila_de_suspeitos_mesmo_com_confianca_maxima():
    classificacao = Classificacao(Etapa.SUSPEITO, 1.0, Motivo.DOMINIO_IMITA_PLATAFORMA)
    decisao = decidir(classificacao, False, "aplicada_confirmada", POLITICA)
    assert decisao.fila is Etapa.SUSPEITO
    assert decisao.estado_novo is None


def test_nao_autenticado_nunca_muda_estado_mesmo_acima_do_limiar():
    decisao = decidir(_reconhecida(Etapa.OFERTA, 1.0), False, "entrevista", POLITICA)
    assert decisao.fila is Etapa.CLASSIFICAR
    assert decisao.estado_novo is None
    assert decisao.motivo is MotivoFila.NAO_AUTENTICADO


def test_sem_vaga_associada_vai_para_classificar():
    decisao = decidir(_reconhecida(Etapa.TESTE), True, None, POLITICA)
    assert decisao.fila is Etapa.CLASSIFICAR
    assert decisao.motivo is MotivoFila.SEM_VAGA


@pytest.mark.parametrize("estado", ["descoberta", "aguardando_aprovacao", "aprovada"])
def test_transicao_fora_da_maquina_de_estados_vai_para_classificar(estado):
    decisao = decidir(_reconhecida(Etapa.ENTREVISTA), True, estado, POLITICA)
    assert decisao.fila is Etapa.CLASSIFICAR
    assert decisao.estado_novo is None
    assert decisao.motivo is MotivoFila.TRANSICAO_INVALIDA


def test_email_atrasado_nao_faz_a_vaga_regredir():
    decisao = decidir(_reconhecida(Etapa.APLICADA), True, "entrevista", POLITICA)
    assert decisao.fila is Etapa.CLASSIFICAR
    assert decisao.motivo is MotivoFila.TRANSICAO_INVALIDA


def test_mesmo_estado_aplica_o_evento_sem_mudar_a_vaga():
    decisao = decidir(_reconhecida(Etapa.TESTE), True, "teste", POLITICA)
    assert decisao.fila is None
    assert decisao.estado_novo is None


def test_encerramento_vale_de_qualquer_etapa_depois_da_candidatura():
    for estado in ("aplicada_confirmada", "teste", "entrevista", "oferta"):
        decisao = decidir(_reconhecida(Etapa.ENCERRADA), True, estado, POLITICA)
        assert decisao.estado_novo == "encerrada"


def test_origens_vem_do_config():
    restrita = replace(POLITICA, origens_permitidas={**POLITICA.origens_permitidas, "teste": ()})
    decisao = decidir(_reconhecida(Etapa.TESTE), True, "aplicada_confirmada", restrita)
    assert decisao.motivo is MotivoFila.TRANSICAO_INVALIDA
