from __future__ import annotations

import re

from src.config import RAIZ, carregar
from src.email.modelo import Etapa
from src.email.regras import regras
from src.email.rotulos import rotulo_da_etapa

ENDERECO_PESSOAL = re.compile(r"[\w.+-]+@(gmail|hotmail|outlook|yahoo|icloud)\.", re.IGNORECASE)


def test_toda_etapa_tem_rotulo():
    for etapa in Etapa:
        assert rotulo_da_etapa(etapa).startswith("Candidaturas/")


def test_rotulos_seguem_a_lista_da_adr_0013():
    esperados = {
        "Candidaturas/Aplicadas",
        "Candidaturas/Teste",
        "Candidaturas/Entrevista",
        "Candidaturas/Oferta",
        "Candidaturas/Encerradas",
        "Candidaturas/Classificar",
        "Candidaturas/Suspeitos",
    }
    assert {rotulo_da_etapa(e) for e in Etapa} == esperados


def test_etapas_do_enum_sao_as_do_rotulos_yaml():
    assert {e.value for e in Etapa} == set(carregar("rotulos")["etapas"])


def test_etapas_com_padrao_em_emails_yaml_existem_no_enum():
    for nome in carregar("emails")["etapas"]:
        assert Etapa(nome) not in (Etapa.CLASSIFICAR, Etapa.SUSPEITO)


def test_regras_refletem_o_arquivo_de_config():
    bruto = carregar("emails")
    atual = regras()
    assert atual.limiar_confianca == bruto["limiar_confianca"]
    assert atual.margem_ambiguidade == bruto["margem_ambiguidade"]
    assert set(atual.plataformas) == set(bruto["plataformas"])


def test_autenticacao_e_lista_de_permissao_com_dmarc_pass():
    assert carregar("emails")["autenticacao_aprovada"] == ["dmarc=pass"]
    assert regras().autenticacao_aprovada == ("dmarc=pass",)


def test_plataforma_dos_alertas_de_vagas_vem_de_config():
    assert regras().plataforma_alertas in regras().plataformas


def test_limiar_e_rigoroso():
    assert regras().limiar_confianca >= 0.9


def test_configs_de_email_nao_tem_endereco_pessoal():
    for nome in ("emails.yaml", "rotulos.yaml"):
        texto = (RAIZ / "config" / nome).read_text(encoding="utf-8")
        assert not ENDERECO_PESSOAL.search(texto)


def test_dominios_configurados_sao_dominios_nao_enderecos():
    for plataforma in regras().plataformas.values():
        assert plataforma.dominios
        for dominio in plataforma.dominios:
            assert "@" not in dominio
            assert dominio == dominio.lower()
