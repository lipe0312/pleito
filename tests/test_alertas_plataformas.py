from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from src.coletor.alertas.extratores import (
    EXTRATORES,
    FormatoDesconhecido,
    extrair_vagas,
)
from src.coletor.alertas_cartao import extrair_cartoes
from src.coletor.alertas_coleta import configuracao_coleta, rodada_alertas
from src.coletor.alertas_config import AlertasMalConfigurado, configuracao_alertas, montar
from src.coletor.alertas_gatilho import (
    RegraGatilho,
    TipoAlerta,
    classificar_alerta,
    plataforma_mencionada,
)
from src.coletor.contratos import VagaBruta
from src.config import carregar
from src.email.modelo import Email
from src.email.regras import regras
from tests.apoio_alertas import DestinoFalso, caso, casos
from tests.test_email_organizador import GmailFalso

ALERTAS = configuracao_alertas()
LIMITE = ALERTAS.corpo_max_chars
PLATAFORMAS = ("gupy", "solides")
AGORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
URL_ESPERADA = {
    "gupy": {
        "2000000001": "https://empresaficticia-alfa.gupy.io/jobs/2000000001",
        "2000000002": "https://empresaficticia-beta.gupy.io/jobs/2000000002",
    },
    "solides": {
        "3000000001": "https://vagas.solides.com.br/vaga/3000000001",
        "3000000002": "https://vagas.solides.com.br/vaga/3000000002",
    },
}
NAO_ALERTAS = (
    "confirmacao_de_candidatura",
    "teste_tecnico",
    "convite_de_entrevista",
    "marketing_com_vaga_em_destaque",
    "pesquisa_de_satisfacao",
)


def _casos():
    return [(p, c) for p in PLATAFORMAS for c in casos(p)]


@pytest.mark.parametrize(("plataforma", "c"), _casos(), ids=lambda v: getattr(v, "nome", v))
def test_gatilho_decide_o_tipo_e_a_regra_de_cada_fixture(plataforma, c):
    resultado = classificar_alerta(c.email, ALERTAS.plataformas[plataforma])
    esperado = c.esperado
    assert resultado.plataforma == plataforma
    assert resultado.tipo.value == esperado["tipo"]
    assert resultado.regra.value == esperado["regra"]
    assert len(resultado.cartoes) == esperado["completos"]
    assert len(resultado.descartados) == esperado["descartados"]
    assert [d.motivo for d in resultado.descartados] == esperado.get("motivos", [])


@pytest.mark.parametrize(("plataforma", "c"), _casos(), ids=lambda v: getattr(v, "nome", v))
def test_plataforma_do_email_e_achada_pela_marca_do_remetente(plataforma, c):
    achada = plataforma_mencionada(c.email, ALERTAS)
    assert achada is not None and achada.nome == plataforma


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_alerta_com_duas_vagas_vira_duas_vaga_bruta(plataforma):
    c = caso("alerta_com_duas_vagas", plataforma)
    config = ALERTAS.plataformas[plataforma]
    resultado = classificar_alerta(c.email, config)
    assert resultado.tipo is TipoAlerta.ALERTA_VAGA
    vagas = extrair_vagas(c.corpo, config, date(2026, 10, 23), LIMITE)
    assert len(vagas) == 2
    assert all(isinstance(v, VagaBruta) for v in vagas)
    assert {v.id_externo: v.url for v in vagas} == URL_ESPERADA[plataforma]
    assert {v.fonte for v in vagas} == {config.fonte}
    assert all(v.titulo and v.empresa and v.local for v in vagas)
    assert all(v.descricao == "" and v.publicada_em == date(2026, 10, 23) for v in vagas)
    for vaga in vagas:
        for rastro in ("?", "utm", "jobBoardSource"):
            assert rastro not in vaga.url


def test_campos_do_cartao_da_gupy_e_da_solides():
    gupy = extrair_vagas(
        caso("alerta_com_duas_vagas", "gupy").corpo, ALERTAS.plataformas["gupy"], None, LIMITE
    )
    assert (gupy[0].titulo, gupy[0].empresa, gupy[0].local) == (
        "Estagio em Engenharia de Dados",
        "Empresa Ficticia Alfa",
        "Recife - PE",
    )
    solides = extrair_vagas(
        caso("alerta_com_duas_vagas", "solides").corpo,
        ALERTAS.plataformas["solides"],
        None,
        LIMITE,
    )
    assert (solides[1].titulo, solides[1].empresa, solides[1].local) == (
        "Analista Junior de Dados",
        "Empresa Ficticia Epsilon",
        "Remoto",
    )


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
@pytest.mark.parametrize("nome", NAO_ALERTAS)
def test_confirmacao_teste_convite_e_marketing_da_plataforma_nunca_geram_vaga(plataforma, nome):
    c = caso(nome, plataforma)
    config = ALERTAS.plataformas[plataforma]
    assert len(extrair_cartoes(c.corpo, config, LIMITE).completos) == 1
    resultado = classificar_alerta(c.email, config)
    assert resultado.tipo in {TipoAlerta.RETORNO, TipoAlerta.OUTRO}
    assert resultado.cartoes == ()


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_confirmacao_de_candidatura_vira_retorno_para_o_f1_2_e_nao_vaga(plataforma):
    c = caso("confirmacao_de_candidatura", plataforma)
    resultado = classificar_alerta(c.email, ALERTAS.plataformas[plataforma])
    assert resultado.tipo is TipoAlerta.RETORNO
    assert resultado.regra is RegraGatilho.ETAPA_RETORNO


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
@pytest.mark.parametrize(
    "nome", ["confirmacao_de_candidatura", "teste_tecnico", "convite_de_entrevista"]
)
def test_sem_o_padrao_de_etapa_o_retorno_da_plataforma_viraria_alerta(plataforma, nome):
    c = caso(nome, plataforma)
    config = ALERTAS.plataformas[plataforma]
    sem_etapas = replace(regras(), etapas={})
    aberta = replace(config, exige_assunto_alerta=False)
    assert classificar_alerta(c.email, aberta, sem_etapas).tipo is TipoAlerta.ALERTA_VAGA
    assert classificar_alerta(c.email, config).tipo is TipoAlerta.RETORNO


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
@pytest.mark.parametrize("nome", ["marketing_com_vaga_em_destaque", "pesquisa_de_satisfacao"])
def test_sem_assunto_nunca_vaga_o_marketing_da_plataforma_viraria_alerta(plataforma, nome):
    c = caso(nome, plataforma)
    config = ALERTAS.plataformas[plataforma]
    sem_regra = replace(config, assunto_nunca_vaga=(), exige_assunto_alerta=False)
    assert classificar_alerta(c.email, sem_regra).tipo is TipoAlerta.ALERTA_VAGA
    resultado = classificar_alerta(c.email, config)
    assert resultado.tipo is TipoAlerta.OUTRO
    assert resultado.regra is RegraGatilho.ASSUNTO_NUNCA_VAGA


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_sem_caixa_nunca_vaga_o_email_de_marketing_viraria_alerta(plataforma):
    c = caso("caixa_de_marketing", plataforma)
    config = ALERTAS.plataformas[plataforma]
    caixa = c.remetente.split("<")[1].split("@")[0]
    sem_regra = replace(
        config,
        caixas_nunca_vaga=tuple(x for x in config.caixas_nunca_vaga if x != caixa),
        caixas_alerta=(*config.caixas_alerta, caixa),
    )
    assert classificar_alerta(c.email, sem_regra).tipo is TipoAlerta.ALERTA_VAGA
    resultado = classificar_alerta(c.email, config)
    assert resultado.tipo is TipoAlerta.OUTRO
    assert resultado.regra is RegraGatilho.CAIXA_NUNCA_VAGA


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
@pytest.mark.parametrize(
    "modelo",
    ["remetente_{}_com_golpe_io", "dmarc_fail", "nome_de_exibicao_de_{}_em_dominio_alheio"],
)
def test_remetente_forjado_vira_suspeito_mesmo_com_cartoes_validos(plataforma, modelo):
    c = caso(modelo.format(plataforma), plataforma)
    config = ALERTAS.plataformas[plataforma]
    assert len(extrair_cartoes(c.corpo, config, LIMITE).completos) >= 1
    resultado = classificar_alerta(c.email, config)
    assert resultado.tipo is TipoAlerta.SUSPEITO
    assert resultado.regra is RegraGatilho.REMETENTE_SUSPEITO
    assert resultado.cartoes == ()


def test_solides_com_dominio_solides_com_golpe_io_vira_suspeito():
    email = Email(
        remetente="Solides <system@solides.com.golpe.io>",
        assunto="Novas vagas para o seu perfil",
        corpo=caso("alerta_com_duas_vagas", "solides").corpo,
        autenticacao="mx.exemplo.com; dmarc=pass",
    )
    config = plataforma_mencionada(email, ALERTAS)
    assert config is not None and config.nome == "solides"
    resultado = classificar_alerta(email, config)
    assert resultado.tipo is TipoAlerta.SUSPEITO
    assert resultado.cartoes == ()


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
@pytest.mark.parametrize("dominio_extra", [".golpe.io", ".com", "-vagas.com"])
def test_dominio_nao_exato_nunca_e_alerta(plataforma, dominio_extra):
    base = caso("alerta_com_duas_vagas", plataforma).email
    dominio = carregar("emails")["plataformas"][plataforma]["dominios"][0]
    caixa = carregar("alertas")["plataformas"][plataforma]["caixas_alerta"][0]
    email = replace(base, remetente=f"{caixa}@{dominio}{dominio_extra}")
    config = ALERTAS.plataformas[plataforma]
    assert classificar_alerta(email, config).tipo is TipoAlerta.SUSPEITO


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
@pytest.mark.parametrize("cabecalho", ["", "mx; dmarc=none", "mx; dmarc=softfail", "dkim=pass"])
def test_so_dmarc_pass_libera_o_alerta_da_plataforma(plataforma, cabecalho):
    base = caso("alerta_com_duas_vagas", plataforma).email
    email = replace(base, autenticacao=cabecalho)
    resultado = classificar_alerta(email, ALERTAS.plataformas[plataforma])
    assert resultado.tipo is TipoAlerta.SUSPEITO


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_injecao_no_corpo_nao_muda_a_classificacao(plataforma):
    config = ALERTAS.plataformas[plataforma]
    for injetado, limpo in (
        ("injecao_no_corpo_de_marketing", "marketing_com_vaga_em_destaque"),
        ("injecao_no_corpo_de_alerta_vazio", "alerta_sem_vaga_nova"),
        ("injecao_forjada_com_dmarc_no_corpo", f"remetente_{plataforma}_com_golpe_io"),
    ):
        a = classificar_alerta(caso(injetado, plataforma).email, config)
        b = classificar_alerta(caso(limpo, plataforma).email, config)
        assert (a.tipo, a.regra) == (b.tipo, b.regra), injetado
        assert a.cartoes == ()


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_injecao_no_corpo_nao_cria_vaga_nem_com_link_da_plataforma(plataforma):
    config = ALERTAS.plataformas[plataforma]
    for nome in (
        "injecao_no_corpo_de_marketing",
        "injecao_no_corpo_de_alerta_vazio",
        "injecao_forjada_com_dmarc_no_corpo",
    ):
        c = caso(nome, plataforma)
        assert classificar_alerta(c.email, config).cartoes == ()
    vazio = caso("injecao_no_corpo_de_alerta_vazio", plataforma)
    assert extrair_vagas(vazio.corpo, config, None, LIMITE) == []


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_cartao_incompleto_devolve_alerta_vazio_e_nunca_vaga_incompleta(plataforma):
    nome = next(n for n in (c.nome for c in casos(plataforma)) if n.startswith("so_cartao_sem_"))
    c = caso(nome, plataforma)
    config = ALERTAS.plataformas[plataforma]
    resultado = classificar_alerta(c.email, config)
    assert resultado.tipo is TipoAlerta.ALERTA_VAZIO
    assert resultado.regra is RegraGatilho.ALERTA_SEM_CARTAO
    assert extrair_vagas(c.corpo, config, None, LIMITE) == []


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_cartao_incompleto_junto_de_completo_so_perde_o_incompleto(plataforma):
    nome = next(n for n in (c.nome for c in casos(plataforma)) if n.startswith("cartao_sem_"))
    c = caso(nome, plataforma)
    config = ALERTAS.plataformas[plataforma]
    vagas = extrair_vagas(c.corpo, config, None, LIMITE)
    assert len(vagas) == 1
    assert all(v.titulo and v.empresa and v.local for v in vagas)


def test_cada_plataforma_usa_um_extrator_do_formato_do_config():
    formatos = {nome: ALERTAS.plataformas[nome].formato for nome in PLATAFORMAS}
    assert formatos["gupy"] != formatos["solides"]
    assert set(formatos.values()) <= set(EXTRATORES)
    assert {p.formato for p in ALERTAS.plataformas.values()} <= set(EXTRATORES)


def test_formato_errado_nao_extrai_o_cartao_da_outra_plataforma():
    gupy = ALERTAS.plataformas["gupy"]
    solides = ALERTAS.plataformas["solides"]
    corpo_gupy = caso("alerta_com_duas_vagas", "gupy").corpo
    corpo_solides = caso("alerta_com_duas_vagas", "solides").corpo
    assert extrair_vagas(corpo_solides, gupy, None, LIMITE) == []
    assert extrair_vagas(corpo_gupy, solides, None, LIMITE) == []


def test_formato_desconhecido_e_recusado():
    desconhecido = replace(ALERTAS.plataformas["gupy"], formato="inventado")
    with pytest.raises(FormatoDesconhecido):
        extrair_vagas("x", desconhecido, None, LIMITE)


def test_extrator_do_bloco_rotulado_nao_pega_campo_do_cartao_anterior():
    config = ALERTAS.plataformas["solides"]
    corpo = (
        "Vaga: Estagio A\nEmpresa: Empresa A\nLocal: Recife\n"
        "Ver vaga: https://vagas.solides.com.br/vaga/1\n"
        "Vaga: Estagio B\nLocal: Recife\n"
        "Ver vaga: https://vagas.solides.com.br/vaga/2\n"
    )
    resultado = extrair_cartoes(corpo, config, LIMITE)
    assert [c.id_vaga for c in resultado.completos] == ["1"]
    assert [(d.id_vaga, d.motivo) for d in resultado.descartados] == [("2", "empresa_ausente")]


def test_link_de_vaga_de_outro_dominio_nao_e_cartao_na_gupy_nem_na_solides():
    gupy = ALERTAS.plataformas["gupy"]
    solides = ALERTAS.plataformas["solides"]
    falso_gupy = "T\nE\nL\nVer vaga: https://empresa.gupy.io.golpe.io/jobs/1\n"
    falso_solides = (
        "Vaga: T\nEmpresa: E\nLocal: L\nVer vaga: https://vagas.solides.com.br.golpe.io/vaga/1\n"
    )
    assert extrair_cartoes(falso_gupy, gupy, LIMITE).completos == ()
    assert extrair_cartoes(falso_solides, solides, LIMITE).completos == ()


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_url_da_vaga_nunca_leva_parametro_de_rastreio_nem_o_texto_do_email(plataforma):
    config = ALERTAS.plataformas[plataforma]
    vagas = extrair_vagas(caso("alerta_com_duas_vagas", plataforma).corpo, config, None, LIMITE)
    for vaga in vagas:
        assert vaga.url == URL_ESPERADA[plataforma][vaga.id_externo]


def _mensagens(plataforma, nomes):
    return [c.mensagem(f"{plataforma}-{c.nome}") for c in casos(plataforma) if c.nome in nomes]


def test_rodada_grava_so_as_vagas_dos_alertas_da_gupy_e_da_solides(tmp_path):
    cfg = configuracao_coleta(tmp_path / "cursor.json", tmp_path / "lidos.jsonl")
    mensagens = [m for p in PLATAFORMAS for m in _mensagens(p, {c.nome for c in casos(p)})]
    destino = DestinoFalso()
    resumo = rodada_alertas(GmailFalso(mensagens), cfg, AGORA, destino)
    esperadas = {url for p in PLATAFORMAS for url in URL_ESPERADA[p].values()}
    assert {v.url for v in destino.vagas} == esperadas
    assert len(destino.vagas) == len(esperadas)
    assert {v.fonte for v in destino.vagas} == {ALERTAS.plataformas[p].fonte for p in PLATAFORMAS}
    assert resumo.lidos == sum(len(casos(p)) for p in PLATAFORMAS)


def test_rodada_com_so_retorno_e_marketing_nao_grava_vaga(tmp_path):
    cfg = configuracao_coleta(tmp_path / "cursor.json", tmp_path / "lidos.jsonl")
    mensagens = [m for p in PLATAFORMAS for m in _mensagens(p, set(NAO_ALERTAS))]
    destino = DestinoFalso()
    resumo = rodada_alertas(GmailFalso(mensagens), cfg, AGORA, destino)
    assert destino.vagas == []
    assert resumo.vagas_enviadas == 0
    assert resumo.por_tipo[TipoAlerta.RETORNO] == 6


def test_config_cobre_gupy_e_solides_com_dominio_exato_do_f1_2():
    emails = carregar("emails")["plataformas"]
    for nome in PLATAFORMAS:
        plataforma = ALERTAS.plataformas[nome]
        assert nome in emails
        assert set(plataforma.caixas_alerta) <= set(emails[nome]["caixas"])
        assert plataforma.cartao_minimo == ("titulo", "empresa", "local")
        assert plataforma.link_canonico.startswith("https://")


def test_consulta_inicial_cobre_o_dominio_de_cada_plataforma_coberta():
    consulta = ALERTAS.consulta_inicial
    emails = carregar("emails")["plataformas"]
    for nome in ALERTAS.plataformas:
        for dominio in emails[nome]["dominios"]:
            assert dominio in consulta


def test_plataforma_sem_cobertura_continua_sem_alerta():
    inhire = Email(
        "no-reply@ses-mail.inhire.app",
        "Novas vagas",
        "x",
        autenticacao="mx.exemplo.com; dmarc=pass",
    )
    assert plataforma_mencionada(inhire, ALERTAS) is None


def _bruto() -> dict:
    return carregar("alertas")


def _com(plataforma: str, **mudancas) -> dict:
    bruto = _bruto()
    return {
        **bruto,
        "plataformas": {plataforma: {**bruto["plataformas"][plataforma], **mudancas}},
    }


def test_config_recusa_link_sem_grupo_id():
    with pytest.raises(AlertasMalConfigurado):
        montar(_com("gupy", link_vaga=r"https://([a-z0-9-]+)\.gupy\.io/jobs/(\d+)"))


def test_config_recusa_canonico_com_placeholder_fora_do_link():
    with pytest.raises(AlertasMalConfigurado):
        montar(_com("gupy", link_canonico="https://{empresa}.gupy.io/jobs/{id}/{outro}"))


def test_config_recusa_formato_sem_nome():
    bruto = _bruto()
    sem_formato = {k: v for k, v in bruto["plataformas"]["gupy"].items() if k != "formato"}
    with pytest.raises(AlertasMalConfigurado):
        montar({**bruto, "plataformas": {"gupy": sem_formato}})


def test_config_recusa_bloco_rotulado_sem_rotulos_de_todos_os_campos():
    with pytest.raises(AlertasMalConfigurado):
        montar(_com("solides", rotulos_campos={"titulo": ["vaga"]}))


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_aviso_de_processo_com_vaga_sugerida_no_fim_nao_vira_vaga(plataforma):
    c = caso("aviso_de_processo_com_vaga_sugerida", plataforma)
    config = ALERTAS.plataformas[plataforma]
    assert len(extrair_cartoes(c.corpo, config, LIMITE).completos) == 1
    resultado = classificar_alerta(c.email, config)
    assert resultado.tipo is TipoAlerta.OUTRO
    assert resultado.regra is RegraGatilho.RESTO
    assert resultado.cartoes == ()


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_sem_exigir_assunto_de_alerta_o_aviso_de_processo_viraria_vaga(plataforma):
    c = caso("aviso_de_processo_com_vaga_sugerida", plataforma)
    config = replace(ALERTAS.plataformas[plataforma], exige_assunto_alerta=False)
    assert classificar_alerta(c.email, config).tipo is TipoAlerta.ALERTA_VAGA


def test_so_o_linkedin_dispensa_o_assunto_de_alerta():
    assert {n: p.exige_assunto_alerta for n, p in ALERTAS.plataformas.items()} == {
        "linkedin": False,
        "gupy": True,
        "solides": True,
    }


@pytest.mark.parametrize("plataforma", PLATAFORMAS)
def test_alerta_sem_vaga_nova_continua_alerta_vazio_com_assunto_exigido(plataforma):
    c = caso("alerta_sem_vaga_nova", plataforma)
    assert classificar_alerta(c.email, ALERTAS.plataformas[plataforma]).tipo is (
        TipoAlerta.ALERTA_VAZIO
    )


def test_link_incompleto_antes_do_cartao_completo_do_mesmo_id_nao_perde_a_vaga_na_gupy():
    config = ALERTAS.plataformas["gupy"]
    link = "Ver vaga: https://empresaficticia-alfa.gupy.io/jobs/2000000001"
    corpo = f"Suas vagas\n{link}\n\nEstagio X\nEmpresa Y\nRecife - PE\n{link}\n"
    resultado = extrair_cartoes(corpo, config, LIMITE)
    assert [c.id_vaga for c in resultado.completos] == ["2000000001"]
    assert resultado.completos[0].titulo == "Estagio X"
    assert resultado.descartados == ()


def test_link_incompleto_antes_do_cartao_completo_do_mesmo_id_nao_perde_a_vaga_na_solides():
    config = ALERTAS.plataformas["solides"]
    link = "Ver vaga: https://vagas.solides.com.br/vaga/3000000001"
    corpo = f"{link}\n\nVaga: Estagio X\nEmpresa: Empresa Y\nLocal: Recife\n{link}\n"
    resultado = extrair_cartoes(corpo, config, LIMITE)
    assert [c.id_vaga for c in resultado.completos] == ["3000000001"]
    assert resultado.descartados == ()


def test_id_so_incompleto_continua_descartado_uma_vez():
    config = ALERTAS.plataformas["solides"]
    link = "Ver vaga: https://vagas.solides.com.br/vaga/3000000001"
    resultado = extrair_cartoes(f"{link}\n{link}\n", config, LIMITE)
    assert resultado.completos == ()
    assert [d.id_vaga for d in resultado.descartados] == ["3000000001"]


def test_dois_cartoes_colados_com_o_segundo_sem_local_descarta_o_segundo_sem_trocar_campos():
    config = ALERTAS.plataformas["gupy"]
    corpo = (
        "Estagio A\nEmpresa A\nRecife - PE\n"
        "Ver vaga: https://a.gupy.io/jobs/1\n"
        "Estagio B\nEmpresa B\n"
        "Ver vaga: https://b.gupy.io/jobs/2\n"
    )
    resultado = extrair_cartoes(corpo, config, LIMITE)
    assert [(c.id_vaga, c.titulo, c.empresa, c.local) for c in resultado.completos] == [
        ("1", "Estagio A", "Empresa A", "Recife - PE")
    ]
    assert [(d.id_vaga, d.motivo) for d in resultado.descartados] == [("2", "local_ausente")]


def test_cartao_colado_nao_usa_campos_do_cartao_anterior_para_completar_o_seguinte():
    config = ALERTAS.plataformas["gupy"]
    corpo = (
        "Estagio A\nEmpresa A\nRecife - PE\n"
        "Ver vaga: https://a.gupy.io/jobs/1\n"
        "Empresa B\n"
        "Ver vaga: https://b.gupy.io/jobs/2\n"
    )
    resultado = extrair_cartoes(corpo, config, LIMITE)
    assert [c.id_vaga for c in resultado.completos] == ["1"]
    assert [d.id_vaga for d in resultado.descartados] == ["2"]
