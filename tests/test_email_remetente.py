from __future__ import annotations

import pytest

from src.email.modelo import Email
from src.email.remetente import (
    endereco_de,
    motivo_forjado,
    plataforma_de,
    remetente_confiavel,
)


def _email(remetente: str, reply_to: str = "", autenticacao: str = "") -> Email:
    return Email(
        remetente=remetente,
        assunto="Assunto",
        corpo="Corpo",
        reply_to=reply_to,
        autenticacao=autenticacao,
    )


@pytest.mark.parametrize(
    "remetente",
    [
        "jobs-noreply@linkedin.com",
        "JOBS-NOREPLY@LINKEDIN.COM",
        "jobalerts-noreply@linkedin.com",
        "LinkedIn <jobs-noreply@linkedin.com>",
    ],
)
def test_remetente_do_linkedin_e_aceito(remetente):
    assert remetente_confiavel(remetente, "linkedin")
    assert plataforma_de(remetente) == "linkedin"


@pytest.mark.parametrize(
    ("remetente", "plataforma"),
    [
        ("no-reply@gupy.com.br", "gupy"),
        ("system@solides.com", "solides"),
        ("qualquer-coisa@ses-mail.inhire.app", "inhire"),
    ],
)
def test_plataformas_do_plano_sao_reconhecidas_pelo_dominio_exato(remetente, plataforma):
    assert plataforma_de(remetente) == plataforma
    assert remetente_confiavel(remetente)


@pytest.mark.parametrize(
    "remetente",
    [
        "golpe@nao-linkedin.com",
        "jobs-noreply@linkedin.com.golpe.net",
        "phishing@linkedin.com.br",
        "jobs-noreply@evil.com",
        "jobs-noreply@sub.linkedin.com",
        "jobs-noreply@linkedin.com@evil.com",
        "qualquer@linkedin.com",
        "no-reply@gupy.com.br.golpe.net",
        "no-reply@xgupy.com.br",
        "no-reply@gupy.com.br.",
        "system@solides.com.evil.io",
        "x@inhire.app",
        "x@ses-mail.inhire.app.evil.io",
        "",
    ],
)
def test_remetente_forjado_ou_desconhecido_nao_e_confiavel(remetente):
    assert not remetente_confiavel(remetente, "linkedin")
    assert not remetente_confiavel(remetente)
    assert plataforma_de(remetente) is None


def test_plataforma_exige_a_caixa_configurada_quando_ha_lista():
    assert plataforma_de("outra-caixa@gupy.com.br") is None
    assert plataforma_de("no-reply@gupy.com.br") == "gupy"


def test_confianca_pedida_para_uma_plataforma_nao_vale_para_outra():
    assert not remetente_confiavel("no-reply@gupy.com.br", "linkedin")


def test_endereco_vem_do_ultimo_par_de_colchetes():
    assert endereco_de('"x <jobs-noreply@linkedin.com>" <golpe@evil.com>') == "golpe@evil.com"


@pytest.mark.parametrize(
    "remetente",
    [
        "jobs-noreply@linkedin.com.golpe.net",
        "no-reply@gupy.com.br.golpe.net",
        "x@sub.linkedin.com",
        "x@linkedin.com.br",
        "x@nao-linkedin.com",
        "x@xgupy.com.br",
        "x@inhire.app",
    ],
)
def test_dominio_que_imita_plataforma_e_forjado(remetente):
    assert motivo_forjado(_email(remetente)) is not None


@pytest.mark.parametrize(
    "remetente",
    [
        "LinkedIn Jobs <golpe@evil.com>",
        "Gupy <no-reply@evil.com>",
        "Gupy Recrutamento <rh@empresa-ficticia.example>",
        '"jobs-noreply@linkedin.com" <golpe@evil.com>',
    ],
)
def test_nome_de_exibicao_de_plataforma_com_endereco_de_outro_dominio_e_forjado(remetente):
    assert motivo_forjado(_email(remetente)) is not None


def test_reply_to_de_outro_dominio_em_remetente_de_plataforma_e_forjado():
    legitimo = _email("no-reply@gupy.com.br")
    desviado = _email("no-reply@gupy.com.br", reply_to="Gupy <suporte@gupy-ajuda.net>")
    sem_marca = _email("no-reply@gupy.com.br", reply_to="suporte@ajuda-vagas.example")
    assert motivo_forjado(legitimo) is None
    assert motivo_forjado(desviado) is not None
    assert motivo_forjado(sem_marca) is not None


def test_reply_to_que_imita_plataforma_e_forjado_mesmo_com_remetente_desconhecido():
    imitando = _email("rh@empresa-ficticia.example", reply_to="x@gupy.com.br.golpe.net")
    assert motivo_forjado(imitando) is not None


def test_reply_to_igual_ao_dominio_da_plataforma_e_aceito():
    assert motivo_forjado(_email("no-reply@gupy.com.br", reply_to="ajuda@gupy.com.br")) is None


@pytest.mark.parametrize("autenticacao", ["spf=fail", "dkim=fail", "dmarc=fail", "SPF = FAIL"])
def test_falha_de_autenticacao_e_forjado(autenticacao):
    email = _email("no-reply@gupy.com.br", autenticacao=f"mx.google.com; {autenticacao}")
    assert motivo_forjado(email) is not None


@pytest.mark.parametrize(
    "autenticacao",
    ["dmarc=none", "dmarc=temperror", "dmarc=permerror", "dmarc=neutral", "spf=pass; dkim=pass"],
)
def test_cabecalho_presente_sem_dmarc_pass_e_forjado(autenticacao):
    email = _email("no-reply@gupy.com.br", autenticacao=f"mx.google.com; {autenticacao}")
    assert motivo_forjado(email) is not None


def test_cabecalho_ausente_nao_e_forjado_mas_remetente_fica_para_o_classificador():
    assert motivo_forjado(_email("no-reply@gupy.com.br", autenticacao="")) is None
    assert motivo_forjado(_email("no-reply@gupy.com.br", autenticacao="   ")) is None


@pytest.mark.parametrize(
    "remetente",
    [
        "jobs-noreply@lin\u212aedin.com",
        "no-reply@\u212aupy.com.br",
        "system@\u017folides.com",
        "no-reply@gupy.com.br\uff0e",
        "no-reply@\uff47upy.com.br",
    ],
)
def test_caractere_de_compatibilidade_nao_vira_dominio_de_plataforma(remetente):
    assert plataforma_de(remetente) is None
    assert not remetente_confiavel(remetente)
    assert motivo_forjado(_email(remetente)) is not None


def test_kelvin_no_dominio_nao_passa_como_linkedin():
    remetente = "jobs-noreply@lin\u212aedin.com"
    assert endereco_de(remetente) != "jobs-noreply@linkedin.com"
    assert not remetente_confiavel(remetente, "linkedin")
    assert motivo_forjado(_email(remetente)) is not None


def test_autenticacao_aprovada_nao_e_forjado():
    aprovada = "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
    email = _email("no-reply@gupy.com.br", autenticacao=aprovada)
    assert motivo_forjado(email) is None


@pytest.mark.parametrize("remetente", ["x@linkedın.com", "x@xn--linkedn-q2a.com", "x@gupy.com.br​"])
def test_dominio_com_caractere_fora_do_ascii_ou_punycode_e_forjado(remetente):
    assert motivo_forjado(_email(remetente)) is not None


def test_remetente_de_empresa_comum_nao_e_forjado_so_desconhecido():
    assert motivo_forjado(_email("Fulana <rh@empresa-ficticia.example>")) is None
    assert plataforma_de("rh@empresa-ficticia.example") is None
