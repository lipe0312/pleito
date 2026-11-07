from __future__ import annotations

from dataclasses import replace

from apoio_validador import (
    contexto_com,
    inventario_rico,
    tex_rico,
    vocabulario_ficticio,
)

from src.padroes.configuracao import configuracao_padroes
from src.validador.conteudo import Vaga, validar_conteudo
from src.validador.resultado import Nivel, Regra

PADROES = configuracao_padroes()
RUN_TECNICO = "construir api rest com python flask e postgresql"
VAGA_API = Vaga(
    empresa="Acme Ltda",
    descricao=f"Buscamos pessoa para {RUN_TECNICO} no dia a dia do time de produto.",
)


def _achados(tex, regra, vocabulario=None, idioma="pt", vaga=VAGA_API, padroes=None):
    contexto = contexto_com(idioma, vaga, vocabulario=vocabulario)
    if padroes is not None:
        contexto = replace(contexto, padroes=padroes)
    return [v for v in validar_conteudo(tex, inventario_rico(), contexto) if v.regra is regra]


def _com_bullet(texto, idioma="pt"):
    base = (
        "Mantive filas com \\tech{RabbitMQ}."
        if idioma == "pt"
        else "Maintained queues with \\tech{RabbitMQ}."
    )
    return tex_rico(idioma).replace(base, texto)


def _padroes_com_verbo(verbo, idioma="pt"):
    dados = PADROES.model_dump()
    dados["senioridade_inflada"]["verbos"][idioma].append(verbo)
    return type(PADROES).model_validate(dados)


def test_api_rest_presente_na_vaga_e_no_vocabulario_nao_conta_como_copia():
    tex = _com_bullet("Construir API REST com Python Flask e PostgreSQL.")
    vocabulario = vocabulario_ficticio(
        pt={"siglas": ["api", "rest"], "termos": ["api rest"], "projetos": []}
    )

    sem = _achados(tex, Regra.COPIA_DA_VAGA)
    com = _achados(tex, Regra.COPIA_DA_VAGA, vocabulario)

    assert [v.nivel for v in sem] == [Nivel.INDICIO]
    assert [v.nivel for v in com] == [Nivel.OK]
    assert "vocabulario" in com[0].evidencia


def test_copia_com_palavras_proprias_suficientes_continua_sendo_indicio_mesmo_com_vocabulario():
    longa = (
        "Atuei para manter servicos de dados em ambiente conteinerizado com testes "
        "automatizados e api rest"
    )
    vaga = Vaga(empresa="Acme Ltda", descricao=f"Buscamos {longa} no time.")
    tex = _com_bullet(f"{longa} com \\tech{{RabbitMQ}}.")
    vocabulario = vocabulario_ficticio(pt={"termos": ["api rest"]})

    achados = _achados(tex, Regra.COPIA_DA_VAGA, vocabulario, vaga=vaga)

    assert [v.nivel for v in achados] == [Nivel.INDICIO]
    assert "palavras" in achados[0].evidencia


def test_vocabulario_do_outro_idioma_nao_salva_a_copia():
    tex = _com_bullet("Construir API REST com Python Flask e PostgreSQL.")
    so_en = vocabulario_ficticio(en={"termos": ["api rest", "python flask", "postgresql"]})

    achados = _achados(tex, Regra.COPIA_DA_VAGA, so_en)

    assert [v.nivel for v in achados] == [Nivel.INDICIO]


def test_vocabulario_em_ingles_salva_a_copia_do_documento_em_ingles():
    run = "build api rest with python flask and postgresql"
    vaga = Vaga(empresa="Acme Ltda", descricao=f"We need someone to {run} every day.")
    tex = _com_bullet("Build API REST with Python Flask and PostgreSQL.", "en")
    vocabulario = vocabulario_ficticio(en={"termos": ["api rest", "python flask", "postgresql"]})

    sem = _achados(tex, Regra.COPIA_DA_VAGA, idioma="en", vaga=vaga)
    com = _achados(tex, Regra.COPIA_DA_VAGA, vocabulario, idioma="en", vaga=vaga)

    assert [v.nivel for v in sem] == [Nivel.INDICIO]
    assert [v.nivel for v in com] == [Nivel.OK]


def test_verbo_do_curriculo_base_nao_vira_senioridade_inflada():
    padroes = _padroes_com_verbo("implementei")
    tex = _com_bullet("Implementei filas com \\tech{RabbitMQ}.")
    vocabulario = vocabulario_ficticio(pt={"verbos": ["implementei"]})

    sem = _achados(tex, Regra.SENIORIDADE, padroes=padroes)
    com = _achados(tex, Regra.SENIORIDADE, vocabulario, padroes=padroes)

    assert [v.nivel for v in sem] == [Nivel.BLOQUEIA]
    assert [v.nivel for v in com] == [Nivel.OK]
    assert "vocabulario" in com[0].evidencia


def test_liderei_sem_base_continua_bloqueando_mesmo_com_vocabulario():
    tex = _com_bullet("Liderei o time de filas com \\tech{RabbitMQ}.")
    vocabulario = vocabulario_ficticio(pt={"verbos": ["implementei", "construi"]})

    achados = _achados(tex, Regra.SENIORIDADE, vocabulario)

    assert [v.nivel for v in achados] == [Nivel.BLOQUEIA]
    assert "liderei" in achados[0].detalhe
    assert achados[0].evidencia


def test_vocabulario_nao_salva_senioridade_de_outro_idioma():
    padroes = _padroes_com_verbo("implementei")
    tex = _com_bullet("Implementei filas com \\tech{RabbitMQ}.")
    so_en = vocabulario_ficticio(en={"verbos": ["implementei"]})

    achados = _achados(tex, Regra.SENIORIDADE, so_en, padroes=padroes)

    assert [v.nivel for v in achados] == [Nivel.BLOQUEIA]


def test_vocabulario_ausente_mantem_o_comportamento_do_f25():
    tex = _com_bullet("Liderei o time de filas com \\tech{RabbitMQ}.")

    assert [v.nivel for v in _achados(tex, Regra.SENIORIDADE)] == [Nivel.BLOQUEIA]


def test_vocabulario_que_nao_aparece_no_texto_nao_gera_registro():
    tex = _com_bullet("Mantive filas com \\tech{RabbitMQ} e testes.")
    vocabulario = vocabulario_ficticio(pt={"verbos": ["implementei"], "termos": ["api rest"]})

    for regra in (Regra.COPIA_DA_VAGA, Regra.SENIORIDADE, Regra.TECNOLOGIA):
        assert _achados(tex, regra, vocabulario) == []
