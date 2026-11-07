from __future__ import annotations

import pytest
from apoio_validador import (
    banco_ficticio,
    configuracao_com,
    contexto_com,
    gravar_pdf,
    gravar_pdf_das_entradas,
    inventario_ficticio,
    inventario_rico,
    tex_com_corpo,
    tex_ficticio,
    tex_rico,
    vocabulario_ficticio,
)

from src.validador.configuracao import configuracao_validador
from src.validador.resultado import Nivel, Regra
from src.validador.tecnologias import validar_tecnologias, validar_tecnologias_no_texto
from src.validador.validar import (
    exigir_fonte_valida,
    validar_arquivos,
    validar_curriculo,
    validar_fonte,
)


def _achados(tex, banco=None, config=None, inventario=None):
    return validar_tecnologias(
        tex,
        inventario or inventario_ficticio(),
        config or configuracao_validador(),
        banco=banco,
    )


def _com(texto):
    return tex_com_corpo(f"Experiência com {texto}")


def test_docker_em_texto_puro_sem_ancora_bloqueia():
    achados = _achados(_com("Docker"))

    assert [(v.regra, v.nivel) for v in achados] == [(Regra.TECNOLOGIA, Nivel.BLOQUEIA)]
    assert "Docker" in achados[0].detalhe
    assert achados[0].trecho and achados[0].sugestao
    assert achados[0].evidencia


def test_docker_com_ancora_em_repositorio_ficticio_vira_ok_e_a_evidencia_aparece():
    banco = banco_ficticio(Docker=["topic"])

    achados = _achados(_com("Docker"), banco)

    assert [(v.regra, v.nivel) for v in achados] == [(Regra.TECNOLOGIA, Nivel.OK)]
    assert "proj_repositorio_ficticio" in achados[0].evidencia
    assert "https://example.invalid/topic" in achados[0].evidencia
    assert validar_fonte(_com("Docker"), inventario_ficticio(), banco=banco).aprovado


def test_evidencia_fraca_vira_indicio_com_a_evidencia_e_nao_recusa():
    banco = banco_ficticio(Docker=["readme"])

    resultado = validar_fonte(_com("Docker"), inventario_ficticio(), banco=banco)

    assert resultado.aprovado
    assert [v.nivel for v in resultado.violacoes] == [Nivel.INDICIO]
    assert "readme" in resultado.violacoes[0].evidencia
    assert resultado.violacoes[0].sugestao


def test_uma_evidencia_forte_basta_mesmo_com_outra_fraca():
    banco = banco_ficticio(Docker=["readme", "linguagem"])

    assert [v.nivel for v in _achados(_com("Docker"), banco)] == [Nivel.OK]


def test_origem_fora_da_tabela_de_forca_conta_como_fraca():
    banco = banco_ficticio(Docker=["origem_nova"])

    assert [v.nivel for v in _achados(_com("Docker"), banco)] == [Nivel.INDICIO]


def test_forca_de_cada_origem_vem_da_configuracao():
    banco = banco_ficticio(Docker=["readme"])
    config = configuracao_com(tecnologias__forca_por_origem={"readme": "forte", "topic": "forte"})

    assert [v.nivel for v in _achados(_com("Docker"), banco, config=config)] == [Nivel.OK]


def test_evidencia_de_outra_tecnologia_nao_salva():
    banco = banco_ficticio(Rust=["topic"])

    assert [v.nivel for v in _achados(_com("Docker"), banco)] == [Nivel.BLOQUEIA]


@pytest.mark.parametrize(
    "nome", ["Rust", "Cassandra", "Laravel", "C++", "Node.js", "Grafana", "Docker"]
)
def test_tecnologia_fora_da_lista_curta_antiga_tambem_bloqueia(nome):
    assert nome not in configuracao_validador().tecnologias_conhecidas

    assert [v.nivel for v in _achados(_com(nome))] == [Nivel.BLOQUEIA]


def test_dicionario_amplo_vem_de_config_e_cobre_varias_categorias():
    dicionario = {nome.casefold() for nome in configuracao_validador().dicionario_tecnologias}

    assert {"rust", "docker", "mongodb", "react", "terraform", "grafana"} <= dicionario


def test_dicionario_vazio_na_configuracao_nao_acha_tecnologia_nova():
    config = configuracao_com(tecnologias_conhecidas=[], dicionario_tecnologias=[])

    assert _achados(_com("Docker"), config=config) == []


@pytest.mark.parametrize(
    "texto", ["elixir", "Elixir", "ruby", "Ruby", "RUBY", "oracle", "ORACLE", "prometheus"]
)
def test_nome_que_nao_e_palavra_comum_casa_em_qualquer_caixa(texto):
    achados = _achados(tex_com_corpo(f"Vou usar {texto} no projeto"))

    assert [v.nivel for v in achados] == [Nivel.BLOQUEIA]


@pytest.mark.parametrize("texto", ["go", "GO", "swift", "spring", "express"])
def test_palavra_comum_fora_da_caixa_exata_vira_indicio_e_nunca_ok(texto):
    achados = _achados(tex_com_corpo(f"Vou {texto} para casa"))

    assert [v.nivel for v in achados] == [Nivel.INDICIO]
    assert "palavra comum" in achados[0].evidencia
    assert achados[0].trecho and achados[0].sugestao


@pytest.mark.parametrize("texto", ["go", "swift", "spring", "express"])
def test_palavra_comum_fora_da_caixa_exata_nao_e_salva_nem_pelo_banco(texto):
    banco = banco_ficticio(**{texto.capitalize(): ["topic"]})

    achados = _achados(tex_com_corpo(f"Vou {texto} para casa"), banco)

    assert [v.nivel for v in achados] == [Nivel.INDICIO]


@pytest.mark.parametrize("nome", ["Go", "Swift", "Spring", "Express"])
def test_palavra_comum_na_caixa_do_dicionario_e_tecnologia(nome):
    assert [v.nivel for v in _achados(_com(nome))] == [Nivel.BLOQUEIA]
    assert [v.nivel for v in _achados(_com(nome), banco_ficticio(**{nome: ["topic"]}))] == [
        Nivel.OK
    ]


def test_palavras_comuns_vem_da_configuracao():
    config = configuracao_com(tecnologias__palavras_comuns=[])

    assert [v.nivel for v in _achados(tex_com_corpo("Vou go para casa"), config=config)] == [
        Nivel.BLOQUEIA
    ]


def test_evidencias_mostradas_vem_da_configuracao():
    banco = banco_ficticio(Docker=["topic", "linguagem", "readme"])
    config = configuracao_com(tecnologias__evidencias_mostradas=1)

    achados = _achados(_com("Docker"), banco, config=config)

    assert achados[0].evidencia.count("proj_repositorio_ficticio") == 1


def test_tecnologia_marcada_com_tech_fora_do_inventario_bloqueia_mesmo_com_evidencia_forte():
    banco = banco_ficticio(Docker=["topic"])

    achados = _achados(tex_com_corpo("Usei \\tech{Docker}."), banco)

    assert [v.nivel for v in achados] == [Nivel.BLOQUEIA]


def test_tecnologia_do_inventario_continua_sem_registro():
    assert _achados(tex_com_corpo("Usei \\tech{Python} e PostgreSQL.")) == []


def _curriculo(tmp_path, sobre, vocabulario):
    tex = tex_rico().replace("Estudante de exemplo", f"Estudante de exemplo {sobre}")
    pdf = gravar_pdf_das_entradas(tmp_path, tex)
    contexto = contexto_com(vocabulario=vocabulario)
    return validar_curriculo(tex, inventario_rico(), None, pdf, contexto=contexto)


@pytest.mark.parametrize(
    ("sobre", "vocabulario"),
    [
        ("Docker Dash", {"projetos": ["Docker Dash"]}),
        ("usando Docker Swarm", {"termos": ["usando docker swarm", "docker swarm"]}),
        ("com Docker", {"siglas": ["docker"]}),
        ("com Rust", {"verbos": ["rust"], "termos": ["com rust"]}),
    ],
)
def test_vocabulario_nunca_salva_tecnologia_do_dicionario(tmp_path, sobre, vocabulario):
    resultado = _curriculo(tmp_path, sobre, vocabulario_ficticio(pt=vocabulario))

    assert Regra.TECNOLOGIA in resultado.regras_bloqueadas


def test_pedido_de_equivalencia_nunca_e_salvo_pelo_vocabulario(tmp_path):
    vocabulario = vocabulario_ficticio(pt={"termos": ["kubernetes", "kafka"], "siglas": ["kafka"]})

    resultado = _curriculo(tmp_path, "com Kubernetes e Kafka", vocabulario)

    bloqueadas = [v for v in resultado.bloqueios if v.regra is Regra.TECNOLOGIA]
    assert len(bloqueadas) == 2


def test_tecnologia_do_dicionario_so_vira_ok_com_evidencia_no_banco(tmp_path):
    vocabulario = vocabulario_ficticio(pt={"projetos": ["Docker Dash"]})
    tex = tex_rico().replace("Estudante de exemplo", "Estudante de exemplo Docker Dash")
    pdf = gravar_pdf_das_entradas(tmp_path, tex)
    contexto = contexto_com(vocabulario=vocabulario, banco=banco_ficticio(Docker=["topic"]))

    resultado = validar_curriculo(tex, inventario_rico(), None, pdf, contexto=contexto)

    assert resultado.aprovado
    assert [v.nivel for v in resultado.salvos if v.regra is Regra.TECNOLOGIA] == [Nivel.OK]


def test_tecnologia_no_texto_do_pdf_usa_o_banco_de_evidencias(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Experiencia com Docker"])
    banco = banco_ficticio(Docker=["topic"])

    sem = validar_arquivos(tex_ficticio(), inventario_ficticio(), pdf=pdf)
    com = validar_arquivos(tex_ficticio(), inventario_ficticio(), pdf=pdf, banco=banco)

    assert Regra.TECNOLOGIA in sem.regras_bloqueadas
    assert com.aprovado
    assert [v.nivel for v in com.violacoes] == [Nivel.OK]


def test_texto_do_pdf_com_evidencia_fraca_so_sinaliza():
    banco = banco_ficticio(Docker=["readme"])

    achados = validar_tecnologias_no_texto(
        "Experiencia com Docker", inventario_ficticio(), configuracao_validador(), banco=banco
    )

    assert [v.nivel for v in achados] == [Nivel.INDICIO]


def test_exigir_fonte_valida_do_gerador_continua_recusando_docker_sem_banco():
    from src.validador.resultado import CurriculoInvalido

    with pytest.raises(CurriculoInvalido):
        exigir_fonte_valida(_com("Docker"), inventario_ficticio())


def test_indicio_de_tecnologia_nao_barra_exigir_fonte_valida():
    banco = banco_ficticio(Docker=["readme"])

    exigir_fonte_valida(_com("Docker"), inventario_ficticio(), banco=banco)


def test_inventario_rico_cobre_docker_compose_sem_liberar_docker_puro():
    assert [v.nivel for v in _achados(_com("Docker Compose"), inventario=inventario_rico())] == []
    assert [v.nivel for v in _achados(_com("Docker"), inventario=inventario_rico())] == [
        Nivel.BLOQUEIA
    ]
