from __future__ import annotations

from dataclasses import replace

import pytest

from src.coletor.alertas_cartao import extrair_cartoes
from src.coletor.alertas_config import (
    AlertasMalConfigurado,
    configuracao_alertas,
    montar,
)
from src.coletor.alertas_gatilho import (
    RegraGatilho,
    TipoAlerta,
    classificar_alerta,
    plataforma_mencionada,
)
from src.config import carregar
from src.email.modelo import Email
from src.email.regras import regras
from tests.apoio_alertas import caso, casos

ALERTAS = configuracao_alertas()
LINKEDIN = ALERTAS.plataformas["linkedin"]
AUTENTICADO = "mx.exemplo.com; dmarc=pass"


def _decidir(nome: str, plataforma=LINKEDIN, configuradas=None):
    return classificar_alerta(caso(nome).email, plataforma, configuradas)


@pytest.mark.parametrize("c", casos(), ids=lambda c: c.nome)
def test_gatilho_decide_o_tipo_e_a_regra_de_cada_fixture(c):
    resultado = classificar_alerta(c.email, LINKEDIN)
    esperado = c.esperado
    assert resultado.tipo.value == esperado["tipo"]
    assert resultado.regra.value == esperado["regra"]
    assert len(resultado.cartoes) == esperado["completos"]
    assert len(resultado.descartados) == esperado["descartados"]
    assert [d.motivo for d in resultado.descartados] == esperado.get("motivos", [])


def test_ordem_das_regras_e_a_da_ficha():
    assert [r.value[0] for r in RegraGatilho] == list("1234567")
    assert [r.name for r in RegraGatilho] == [
        "REMETENTE_SUSPEITO",
        "CAIXA_NUNCA_VAGA",
        "ETAPA_RETORNO",
        "ASSUNTO_NUNCA_VAGA",
        "ALERTA_COM_CARTAO",
        "ALERTA_SEM_CARTAO",
        "RESTO",
    ]


def test_so_alerta_vaga_carrega_cartoes():
    for c in casos():
        resultado = classificar_alerta(c.email, LINKEDIN)
        if resultado.tipo is not TipoAlerta.ALERTA_VAGA:
            assert resultado.cartoes == ()


def test_regra_1_remetente_suspeito_vence_mesmo_com_cartoes_validos():
    c = caso("remetente_linkedin_com_golpe_net")
    assert len(extrair_cartoes(c.corpo, LINKEDIN, ALERTAS.corpo_max_chars).completos) == 3
    resultado = classificar_alerta(c.email, LINKEDIN)
    assert resultado.tipo is TipoAlerta.SUSPEITO
    assert resultado.cartoes == ()


def test_regra_1_dmarc_diferente_de_pass_nunca_gera_vaga():
    c = caso("dmarc_fail")
    assert len(extrair_cartoes(c.corpo, LINKEDIN, ALERTAS.corpo_max_chars).completos) == 3
    assert classificar_alerta(c.email, LINKEDIN).tipo is TipoAlerta.SUSPEITO


@pytest.mark.parametrize("cabecalho", ["", "mx; dmarc=none", "mx; dmarc=softfail", "dkim=pass"])
def test_regra_1_so_dmarc_pass_libera(cabecalho):
    base = caso("alerta_com_tres_vagas").email
    email = replace(base, autenticacao=cabecalho)
    assert classificar_alerta(email, LINKEDIN).tipo is TipoAlerta.SUSPEITO


def test_regra_1_dominio_exato_vem_do_f1_2_e_nao_de_substring():
    base = caso("alerta_com_tres_vagas").email
    for remetente in (
        "jobs-noreply@sub.linkedin.com",
        "jobs-noreply@linkedin.com.br",
        "jobs-noreply@nao-linkedin.com",
        "jobs-noreply@linkedin.com@golpe.net",
    ):
        resultado = classificar_alerta(replace(base, remetente=remetente), LINKEDIN)
        assert resultado.tipo is TipoAlerta.SUSPEITO, remetente


def test_regra_1_reply_to_divergente_e_suspeito():
    base = caso("alerta_com_tres_vagas").email
    email = replace(base, reply_to="Suporte <ajuda@golpe.net>")
    assert classificar_alerta(email, LINKEDIN).tipo is TipoAlerta.SUSPEITO


def test_regra_2_sem_caixa_nunca_vaga_o_post_viraria_vaga():
    c = caso("post_com_link_de_vaga")
    caixa = c.remetente.split("@")[0]
    sem_regra = replace(
        LINKEDIN,
        caixas_nunca_vaga=tuple(x for x in LINKEDIN.caixas_nunca_vaga if x != caixa),
        caixas_mensagem_recrutador=(),
        assunto_nunca_vaga=(),
        caixas_alerta=(*LINKEDIN.caixas_alerta, caixa),
    )
    assert classificar_alerta(c.email, sem_regra).tipo is TipoAlerta.ALERTA_VAGA
    assert classificar_alerta(c.email, LINKEDIN).tipo is TipoAlerta.OUTRO


def test_regra_2_mensagem_de_recrutador_tem_tipo_proprio_por_config():
    resultado = _decidir("mensagem_de_recrutador_com_link_de_vaga")
    assert resultado.tipo is TipoAlerta.MENSAGEM_RECRUTADOR
    assert resultado.cartoes == ()
    sem_recrutador = replace(LINKEDIN, caixas_mensagem_recrutador=())
    outro = _decidir("mensagem_de_recrutador_com_link_de_vaga", sem_recrutador)
    assert outro.tipo is TipoAlerta.OUTRO and outro.regra is RegraGatilho.CAIXA_NUNCA_VAGA


def test_regra_2_vence_a_etapa_do_f1_2():
    email = Email(
        remetente="messages-noreply@linkedin.com",
        assunto="Convite para entrevista",
        corpo="Gostariamos de agendar uma entrevista",
        autenticacao=AUTENTICADO,
    )
    resultado = classificar_alerta(email, LINKEDIN)
    assert resultado.regra is RegraGatilho.CAIXA_NUNCA_VAGA
    assert resultado.tipo is TipoAlerta.MENSAGEM_RECRUTADOR


def test_regra_3_sem_o_padrao_de_etapa_o_retorno_viraria_alerta():
    c = caso("retorno_de_candidatura")
    assert classificar_alerta(c.email, LINKEDIN).tipo is TipoAlerta.RETORNO
    sem_etapas = replace(regras(), etapas={})
    assert classificar_alerta(c.email, LINKEDIN, sem_etapas).tipo is TipoAlerta.ALERTA_VAGA


def test_regra_3_vence_o_assunto_nunca_vaga():
    email = Email(
        remetente="jobs-noreply@linkedin.com",
        assunto="Recebemos sua candidatura. Experimente o Premium",
        corpo="",
        autenticacao=AUTENTICADO,
    )
    resultado = classificar_alerta(email, LINKEDIN)
    assert resultado.regra is RegraGatilho.ETAPA_RETORNO
    assert resultado.tipo is TipoAlerta.RETORNO


def test_regra_4_sem_assunto_nunca_vaga_candidatura_vista_viraria_alerta():
    c = caso("candidatura_vista")
    sem_regra = replace(LINKEDIN, assunto_nunca_vaga=())
    assert classificar_alerta(c.email, sem_regra).tipo is TipoAlerta.ALERTA_VAGA
    resultado = classificar_alerta(c.email, LINKEDIN)
    assert resultado.tipo is TipoAlerta.OUTRO
    assert resultado.regra is RegraGatilho.ASSUNTO_NUNCA_VAGA


def test_regra_4_ignora_acento_e_caixa_do_assunto():
    base = caso("candidatura_vista").email
    email = replace(base, assunto="SUA CANDIDATURA FOI VISTA POR EMPRESA")
    assert classificar_alerta(email, LINKEDIN).regra is RegraGatilho.ASSUNTO_NUNCA_VAGA
    email = replace(base, assunto="Verifique seu acesso")
    assert classificar_alerta(email, LINKEDIN).regra is RegraGatilho.ASSUNTO_NUNCA_VAGA


def test_regra_5_sem_caixa_de_alerta_o_cartao_nao_basta():
    c = caso("alerta_com_tres_vagas")
    sem_caixa = replace(LINKEDIN, caixas_alerta=())
    resultado = classificar_alerta(c.email, sem_caixa)
    assert resultado.tipo is TipoAlerta.OUTRO and resultado.regra is RegraGatilho.RESTO
    assert resultado.cartoes == ()


def test_regra_5_alerta_vaga_exige_cartao_completo_pelo_config():
    c = caso("cartao_sem_empresa_junto_de_cartao_completo")
    exigente = replace(LINKEDIN, cartao_minimo=("titulo", "empresa", "local"))
    frouxo = replace(LINKEDIN, cartao_minimo=("titulo",))
    assert len(classificar_alerta(c.email, exigente).cartoes) == 1
    assert len(classificar_alerta(c.email, frouxo).cartoes) == 2


def test_regra_6_caixa_de_alerta_sem_cartao_completo_e_alerta_vazio():
    resultado = _decidir("so_cartao_sem_empresa")
    assert resultado.tipo is TipoAlerta.ALERTA_VAZIO
    assert resultado.regra is RegraGatilho.ALERTA_SEM_CARTAO
    assert resultado.cartoes == ()
    assert [d.motivo for d in resultado.descartados] == ["empresa_ausente"]


def test_regra_7_o_resto_e_outro():
    resultado = _decidir("caixa_desconhecida_do_dominio_exato")
    assert resultado.tipo is TipoAlerta.OUTRO and resultado.regra is RegraGatilho.RESTO


def test_assunto_alerta_nao_decide_nada_so_e_sinal_de_calibracao():
    c = caso("alerta_com_tres_vagas")
    sem_assunto = replace(LINKEDIN, assunto_alerta=())
    assert classificar_alerta(c.email, sem_assunto).tipo is TipoAlerta.ALERTA_VAGA


def test_texto_do_corpo_nao_muda_o_remetente_nem_a_regra():
    resultado = _decidir("injecao_forjada_com_dmarc_no_corpo")
    assert resultado.tipo is TipoAlerta.SUSPEITO
    resultado = _decidir("injecao_no_corpo_de_mensagem")
    assert resultado.tipo is TipoAlerta.MENSAGEM_RECRUTADOR
    assert resultado.cartoes == ()


def test_plataforma_mencionada_so_para_email_que_cita_a_marca():
    ficticio = caso("alerta_com_tres_vagas").email
    assert plataforma_mencionada(ficticio, ALERTAS) is LINKEDIN
    golpe = caso("remetente_linkedin_com_golpe_net").email
    assert plataforma_mencionada(golpe, ALERTAS) is LINKEDIN
    pessoal = Email("amigo@exemplo.com", "Almoco?", "oi", autenticacao=AUTENTICADO)
    assert plataforma_mencionada(pessoal, ALERTAS) is None
    gupy = Email("no-reply@gupy.com.br", "Recebemos sua candidatura", "x", autenticacao=AUTENTICADO)
    assert plataforma_mencionada(gupy, ALERTAS) is None


def test_config_so_tem_caixa_de_alerta_conhecida_do_f1_2():
    emails = carregar("emails")
    for nome, plataforma in ALERTAS.plataformas.items():
        assert nome in emails["plataformas"]
        permitidas = {c.lower() for c in emails["plataformas"][nome]["caixas"]}
        assert set(plataforma.caixas_alerta) <= permitidas


def test_config_usa_a_plataforma_de_alertas_do_f1_2():
    assert regras().plataforma_alertas in ALERTAS.plataformas


def _bruto() -> dict:
    return carregar("alertas")


def test_config_recusa_cartao_minimo_fora_dos_campos():
    bruto = _bruto()
    ruim = {**bruto, "plataformas": {"linkedin": {**bruto["plataformas"]["linkedin"],
                                                  "cartao_minimo": ["salario"]}}}
    with pytest.raises(AlertasMalConfigurado):
        montar(ruim)


def test_config_recusa_caixa_em_alerta_e_em_nunca_vaga():
    bruto = _bruto()
    linkedin = bruto["plataformas"]["linkedin"]
    ruim = {**bruto, "plataformas": {"linkedin": {**linkedin,
            "caixas_nunca_vaga": [*linkedin["caixas_nunca_vaga"], linkedin["caixas_alerta"][0]]}}}
    with pytest.raises(AlertasMalConfigurado):
        montar(ruim)


def test_config_recusa_link_sem_id_da_vaga():
    bruto = _bruto()
    linkedin = bruto["plataformas"]["linkedin"]
    ruim = {**bruto, "plataformas": {"linkedin": {**linkedin, "link_canonico": "https://x/y"}}}
    with pytest.raises(AlertasMalConfigurado):
        montar(ruim)


def test_config_recusa_limite_de_campo_ausente_ou_nao_positivo():
    bruto = _bruto()
    linkedin = bruto["plataformas"]["linkedin"]
    for limites in ({"titulo": 10, "empresa": 10}, {"titulo": 10, "empresa": 0, "local": 10}):
        ruim = {**bruto, "plataformas": {"linkedin": {**linkedin, "limites_campos": limites}}}
        with pytest.raises(AlertasMalConfigurado):
            montar(ruim)
