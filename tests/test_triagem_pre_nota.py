from __future__ import annotations

from datetime import timedelta

from apoio_triagem import HOJE, inventario, vaga

from src.coletor.contratos import ModeloTrabalho, Senioridade
from src.triagem.configuracao import configuracao_triagem
from src.triagem.pre_nota import calcular_pre_nota

CONFIG = configuracao_triagem()
INVENTARIO = inventario()


def _nota(v, config=CONFIG):
    return calcular_pre_nota(v, INVENTARIO, config, HOJE)


def test_vaga_boa_com_techs_do_inventario_remota_e_recente_passa_do_minimo():
    assert _nota(vaga()) >= CONFIG.pre_nota_minima


def test_nota_fica_entre_zero_e_cem():
    piores = vaga(
        descricao="sem tecnologia nenhuma",
        senioridade=Senioridade.SENIOR,
        modelo=ModeloTrabalho.PRESENCIAL,
        pais="JP",
        publicada_em=HOJE - timedelta(days=60),
    )
    assert 0 <= _nota(piores) < _nota(vaga()) <= 100


def test_vaga_sem_tech_do_inventario_fica_abaixo_do_minimo():
    sem_tech = vaga(descricao="Estagio generico, sem pilha informada. " * 6)
    assert _nota(sem_tech) < CONFIG.pre_nota_minima


def test_mais_techs_cobertas_dao_nota_maior():
    uma = vaga(descricao="Pedimos Python. " * 5)
    tres = vaga(descricao="Pedimos Python, PostgreSQL e Docker Compose. " * 5)
    assert _nota(tres) > _nota(uma)


def test_tech_pedida_que_o_inventario_nao_tem_reduz_a_cobertura():
    cobre = vaga(descricao="Pedimos Python, PostgreSQL e Docker Compose. " * 5)
    pede_fora = vaga(descricao="Pedimos Python, PostgreSQL, Docker Compose, Terraform e AWS. " * 5)
    assert _nota(pede_fora) < _nota(cobre)


def test_tech_com_equivalente_honesto_vale_menos_que_a_coberta_e_mais_que_a_ausente():
    coberta = vaga(descricao="Pedimos Python, RabbitMQ e Flask. " * 5)
    equivalente = vaga(descricao="Pedimos Python, Kafka e Flask. " * 5)
    ausente = vaga(descricao="Pedimos Python, Terraform e Flask. " * 5)
    assert _nota(coberta) > _nota(equivalente) > _nota(ausente)


def test_estagio_vale_mais_que_senioridade_indefinida():
    estagio = vaga(senioridade=Senioridade.ESTAGIO)
    indefinida = vaga(senioridade=Senioridade.INDEFINIDA)
    assert _nota(estagio) > _nota(indefinida)


def test_empresa_alvo_soma_o_peso_configurado():
    comum = _nota(vaga(alvo=False))
    alvo = _nota(vaga(alvo=True))
    assert alvo - comum == CONFIG.filtros.pontuacao.peso_empresa_alvo


def test_vaga_antiga_perde_recencia():
    nova = _nota(vaga(publicada_em=HOJE))
    velha = _nota(vaga(publicada_em=HOJE - timedelta(days=20)))
    assert nova > velha


def test_pesos_vem_da_configuracao():
    pesos = CONFIG.filtros.pontuacao.model_copy(update={"peso_stack": 0})
    filtros = CONFIG.filtros.model_copy(update={"pontuacao": pesos})
    sem_stack = CONFIG.model_copy(update={"filtros": filtros})
    sem_tech = vaga(descricao="Estagio generico, sem pilha informada. " * 6)
    assert _nota(sem_tech, sem_stack) > _nota(sem_tech)
