from __future__ import annotations

import pytest

from src.config import carregar
from src.email.classificador import classificar
from src.email.modelo import Email
from src.email.vinculo import montar_regra_vinculo, regra_de_vinculo, vaga_do_email

APROVADA = "mx.exemplo; spf=pass; dkim=pass; dmarc=pass"
REPROVADA = "mx.exemplo; spf=fail; dkim=fail; dmarc=fail"
EMPRESA = "acme.exemplo"
GUPY = "Gupy <no-reply@gupy.com.br>"
ATAQUE = "'; DROP TABLE vaga; --"


class CursorFalso:
    def __init__(self, por_dominio=None, por_plataforma=None):
        self.por_dominio = por_dominio or {}
        self.por_plataforma = por_plataforma or {}
        self.consultas: list[tuple[str, tuple]] = []
        self._linhas: list[tuple] = []

    def execute(self, sql, params=()):
        self.consultas.append((sql, tuple(params)))
        if "candidatura" in sql:
            self._linhas = list(self.por_plataforma.get(params[0], []))
        else:
            self._linhas = list(self.por_dominio.get(params[0], []))

    def fetchall(self):
        return self._linhas


def _vincular(cursor, email: Email):
    return vaga_do_email(cursor, email, classificar(email))


def _da_empresa(remetente: str = f"RH <rh@{EMPRESA}>", **campos) -> Email:
    padrao = {
        "assunto": "Convite para entrevista",
        "corpo": "Gostariamos de agendar uma entrevista.",
        "autenticacao": APROVADA,
    }
    return Email(remetente, **{**padrao, **campos})


def _da_plataforma(assunto: str = "Recebemos sua candidatura na Acme", **campos) -> Email:
    return Email(GUPY, assunto, campos.pop("corpo", ""), autenticacao=APROVADA, **campos)


def test_regra_vem_do_config_e_estados_sao_os_do_config():
    regra = regra_de_vinculo()
    bruto = carregar("eventos_email")["vinculo"]
    assert regra.estados_candidatos == tuple(bruto["estados_candidatos"])
    assert regra.limite_candidatas == bruto["limite_candidatas"]
    assert "gmail.com" in regra.dominios_ignorados


def test_dominio_exato_da_empresa_com_uma_vaga_aberta_vincula():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    assert _vincular(cursor, _da_empresa()) == 11
    sql, params = cursor.consultas[0]
    assert params[0] == EMPRESA
    assert list(params[1]) == list(regra_de_vinculo().estados_candidatos)
    assert params[2] == regra_de_vinculo().limite_candidatas


def test_dominio_em_maiusculas_e_normalizado_antes_de_consultar():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    assert _vincular(cursor, _da_empresa("RH <RH@ACME.Exemplo>")) == 11


def test_duas_vagas_abertas_da_mesma_empresa_ficam_sem_vinculo():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,), (12,)]})
    assert _vincular(cursor, _da_empresa()) is None


def test_empresa_sem_vaga_aberta_fica_sem_vinculo():
    assert _vincular(CursorFalso(), _da_empresa()) is None


@pytest.mark.parametrize(
    "remetente",
    [
        f"RH <rh@{EMPRESA}.golpe.exemplo>",
        f"RH <rh@mail.{EMPRESA}>",
        "RH <rh@acme-exemplo.exemplo>",
        "RH <rh@acmeexemplo.exemplo>",
        "RH <rh@evilacme.exemplo>",
        f"{EMPRESA} <rh@golpe.exemplo>",
        f'"rh@{EMPRESA}" <rh@golpe.exemplo>',
        f"RH <rh@golpe.exemplo, rh@{EMPRESA}>",
        f"rh@golpe.exemplo, rh@{EMPRESA}",
    ],
)
def test_remetente_forjado_nao_vincula_a_empresa(remetente):
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    assert _vincular(cursor, _da_empresa(remetente)) is None


def test_consulta_do_remetente_forjado_leva_o_dominio_inteiro_e_nao_o_da_empresa():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    _vincular(cursor, _da_empresa(f"RH <rh@{EMPRESA}.golpe.exemplo>"))
    assert [params[0] for _, params in cursor.consultas] == [f"{EMPRESA}.golpe.exemplo"]


def test_sem_autenticacao_aprovada_nao_vincula_nem_consulta():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    assert _vincular(cursor, _da_empresa(autenticacao=REPROVADA)) is None
    assert _vincular(cursor, _da_empresa(autenticacao="")) is None
    assert cursor.consultas == []


def test_reply_to_de_outro_dominio_nao_vincula():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    assert _vincular(cursor, _da_empresa(reply_to="Golpe <x@golpe.exemplo>")) is None
    assert cursor.consultas == []


def test_reply_to_do_mesmo_dominio_vincula():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    assert _vincular(cursor, _da_empresa(reply_to=f"RH <contato@{EMPRESA}>")) == 11


def test_classificacao_suspeita_nao_vincula_nem_consulta():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    email = _da_empresa(f"Gupy <rh@{EMPRESA}>")
    assert classificar(email).etapa.value == "suspeito"
    assert _vincular(cursor, email) is None
    assert cursor.consultas == []


def test_dominio_de_email_gratuito_nunca_vincula():
    cursor = CursorFalso(por_dominio={"gmail.com": [(11,)]})
    assert _vincular(cursor, _da_empresa("Fulano <fulano@gmail.com>")) is None
    assert cursor.consultas == []


def test_dominio_ignorado_vem_do_config():
    regra = montar_regra_vinculo(
        {
            "estados_candidatos": ["pendente"],
            "dominios_ignorados": [EMPRESA],
            "limite_candidatas": 5,
        }
    )
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    email = _da_empresa()
    assert vaga_do_email(cursor, email, classificar(email), regra) is None


def test_plataforma_vincula_pela_empresa_citada_no_assunto():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme"), (8, "beta")]})
    assert _vincular(cursor, _da_plataforma()) == 7
    assert cursor.consultas[0][1][0] == "gupy"


def test_plataforma_vincula_pela_empresa_citada_no_corpo_sem_acento_nem_caixa():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "açaí s.a."), (8, "beta")]})
    email = _da_plataforma("Recebemos sua candidatura", corpo="Vaga na AÇAÍ S.A. em Sao Paulo")
    assert _vincular(cursor, email) == 7


def test_plataforma_sem_empresa_citada_fica_sem_vinculo():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme"), (8, "beta")]})
    assert _vincular(cursor, _da_plataforma("Recebemos sua candidatura")) is None


def test_plataforma_com_duas_empresas_citadas_fica_sem_vinculo():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme"), (8, "beta")]})
    assert _vincular(cursor, _da_plataforma("Recebemos sua candidatura Acme e Beta")) is None


def test_plataforma_com_duas_vagas_da_mesma_empresa_fica_sem_vinculo():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme"), (9, "acme")]})
    assert _vincular(cursor, _da_plataforma()) is None


def test_nome_de_empresa_so_casa_como_palavra_inteira():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme")]})
    assert _vincular(cursor, _da_plataforma("Recebemos sua candidatura na Acmecorp")) is None


def test_empresa_sem_nome_nunca_casa():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "")]})
    assert _vincular(cursor, _da_plataforma()) is None


def test_plataforma_sem_autenticacao_aprovada_nao_vincula():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme")]})
    email = Email(GUPY, "Recebemos sua candidatura na Acme", "", autenticacao=REPROVADA)
    assert _vincular(cursor, email) is None
    assert cursor.consultas == []


def test_dominio_imitando_a_plataforma_nao_vincula():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme")]})
    email = Email(
        "Gupy <no-reply@gupy-vagas.exemplo>",
        "Recebemos sua candidatura na Acme",
        "",
        autenticacao=APROVADA,
    )
    assert _vincular(cursor, email) is None
    assert cursor.consultas == []


def test_nome_de_exibicao_de_plataforma_com_dominio_alheio_nao_vincula():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, "acme")]})
    email = Email(
        "Gupy <no-reply@golpe.exemplo>",
        "Recebemos sua candidatura na Acme",
        "",
        autenticacao=APROVADA,
    )
    assert _vincular(cursor, email) is None


def test_plataforma_de_alertas_nao_vincula():
    alertas = carregar("emails")["plataforma_alertas"]
    caixa = carregar("emails")["plataformas"][alertas]["caixas"][0]
    dominio = carregar("emails")["plataformas"][alertas]["dominios"][0]
    cursor = CursorFalso(por_plataforma={alertas: [(7, "acme")]})
    email = Email(
        f"Alertas <{caixa}@{dominio}>", "Vaga na Acme", "Acme contrata", autenticacao=APROVADA
    )
    assert _vincular(cursor, email) is None
    assert cursor.consultas == []


def test_dominio_da_empresa_tem_prioridade_sobre_a_plataforma():
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]}, por_plataforma={"gupy": [(7, "acme")]})
    assert _vincular(cursor, _da_empresa()) == 11


def test_aspas_em_assunto_remetente_e_nome_de_empresa_vao_so_como_parametro():
    cursor = CursorFalso(por_plataforma={"gupy": [(7, ATAQUE.lower())]})
    email = Email(GUPY, f"Recebemos sua candidatura {ATAQUE}", ATAQUE, autenticacao=APROVADA)
    assert _vincular(cursor, email) == 7
    cursor = CursorFalso(por_dominio={EMPRESA: [(11,)]})
    assert _vincular(cursor, _da_empresa(f"{ATAQUE} <rh@{EMPRESA}>", assunto=ATAQUE)) == 11
    for sql, _ in cursor.consultas:
        assert "DROP" not in sql
        assert "'" not in sql
