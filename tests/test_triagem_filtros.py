from __future__ import annotations

from datetime import timedelta

import pytest
from apoio_triagem import HOJE, vaga

from src.coletor.contratos import ModeloTrabalho, Senioridade
from src.triagem.configuracao import configuracao_triagem
from src.triagem.contratos import Motivo
from src.triagem.filtros import motivo_de_descarte

CONFIG = configuracao_triagem()


def _motivo(v):
    achado = motivo_de_descarte(v, CONFIG.filtros, HOJE)
    return None if achado is None else achado[0]


def test_vaga_de_estagio_backend_remoto_passa():
    assert _motivo(vaga()) is None


@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        ({"titulo": "Executivo de Vendas", "descricao": "x" * 300}, Motivo.FUNCAO),
        ({"titulo": "Servicos Gerais", "descricao": ""}, Motivo.FUNCAO),
        ({"senioridade": Senioridade.SENIOR}, Motivo.SENIORIDADE),
        ({"senioridade": Senioridade.PLENO}, Motivo.SENIORIDADE),
        ({"titulo": "Desenvolvedor Backend Sênior"}, Motivo.TITULO),
        ({"titulo": "Software Engineer Lead"}, Motivo.TITULO),
        ({"descricao": "Exigimos 5 anos de experiencia em Python."}, Motivo.ANOS),
        ({"pais": "JP"}, Motivo.PAIS),
        (
            {"modelo": ModeloTrabalho.PRESENCIAL, "local": "Sao Paulo, SP"},
            Motivo.LOCAL,
        ),
        (
            {"modelo": ModeloTrabalho.HIBRIDO, "local": "Curitiba, PR"},
            Motivo.LOCAL,
        ),
        ({"publicada_em": HOJE - timedelta(days=31)}, Motivo.IDADE),
    ],
)
def test_cada_filtro_eliminatorio_devolve_o_seu_motivo(campos, esperado):
    assert _motivo(vaga(**campos)) == esperado


def test_presencial_em_salvador_passa():
    assert _motivo(vaga(modelo=ModeloTrabalho.PRESENCIAL, local="Salvador, BA")) is None


def test_senioridade_indefinida_nao_e_eliminada():
    assert _motivo(vaga(senioridade=Senioridade.INDEFINIDA)) is None


def test_vaga_sem_data_nao_e_eliminada_por_idade():
    assert _motivo(vaga(publicada_em=None)) is None


def test_anos_dentro_do_maximo_passam():
    assert _motivo(vaga(descricao="Desejavel 1 ano de experiencia.")) is None


def test_funcao_vem_antes_da_senioridade():
    achado = _motivo(vaga(titulo="Gerente Comercial", senioridade=Senioridade.SENIOR))
    assert achado == Motivo.FUNCAO


def test_limites_vem_da_configuracao_e_nao_do_codigo():
    rigido = CONFIG.filtros.model_copy(
        update={
            "eliminatorios": CONFIG.filtros.eliminatorios.model_copy(
                update={"idade_maxima_dias": 2}
            )
        }
    )
    antiga = vaga(publicada_em=HOJE - timedelta(days=5))
    assert motivo_de_descarte(antiga, rigido, HOJE)[0] == Motivo.IDADE
    assert motivo_de_descarte(antiga, CONFIG.filtros, HOJE) is None
