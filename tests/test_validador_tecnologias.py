from __future__ import annotations

import pytest
from apoio_validador import (
    configuracao_com,
    gravar_pdf,
    inventario_ficticio,
    tex_com_corpo,
    tex_ficticio,
    tex_minimo,
)

from src.conteudo.modelo import Ancora, Inventario, ItemInventario
from src.validador.configuracao import configuracao_validador
from src.validador.resultado import Regra
from src.validador.tecnologias import validar_tecnologias, validar_tecnologias_no_texto
from src.validador.validar import validar_curriculo


def _regras(tex: str, inventario=None, config=None) -> list[Regra]:
    violacoes = validar_tecnologias(
        tex, inventario or inventario_ficticio(), config or configuracao_validador()
    )
    return [v.regra for v in violacoes]


def _inventario(*techs: str) -> Inventario:
    ancora = Ancora(tipo="disciplina", ref="x", fonte="x")
    return Inventario(techs=[ItemInventario(tech=t, ancoras=[ancora]) for t in techs])


def test_curriculo_so_com_tecnologia_do_inventario_passa():
    assert _regras(tex_ficticio()) == []


@pytest.mark.parametrize(
    "marcada",
    [
        "Cobol",
        "Kubernetes",
        "kubernetes",
        "KUBERNETES",
        "KuBeRnEtEs",
        "Python3",
        "Pyth0n",
        "Flask2",
    ],
)
def test_tecnologia_marcada_fora_do_inventario_e_recusada_em_qualquer_caixa(marcada):
    tex = tex_com_corpo(f"Usei \\tech{{{marcada}}} no projeto.")

    assert Regra.TECNOLOGIA in _regras(tex)


@pytest.mark.parametrize("marcada", ["python", "PYTHON", "postgresql", "Face\\_Recognition"])
def test_variacao_de_caixa_de_tecnologia_do_inventario_e_a_mesma_tecnologia(marcada):
    assert _regras(tex_com_corpo(f"Usei \\tech{{{marcada}}}.")) == []


def test_tecnologia_com_sublinhado_escapado_casa_com_o_inventario():
    assert _regras(tex_com_corpo("Usei \\tech{face\\_recognition}.")) == []


@pytest.mark.parametrize(
    "texto",
    ["Kubernetes", "kubernetes", "KUBERNETES", "Kafka", "kafka", "usei AWS e azure", "Terraform."],
)
def test_tecnologia_conhecida_citada_sem_marcador_e_recusada(texto):
    assert Regra.TECNOLOGIA in _regras(tex_com_corpo(f"Experiência com {texto}"))


def test_tecnologia_conhecida_so_conta_como_palavra_inteira():
    assert _regras(tex_com_corpo("Dados sparkling e kafkaesco.")) == []


def test_pedido_de_equivalencia_do_inventario_nunca_pode_aparecer():
    config = configuracao_com(tecnologias_conhecidas=[])

    assert Regra.TECNOLOGIA in _regras(tex_com_corpo("Experiência com Kafka"), config=config)
    assert Regra.TECNOLOGIA in _regras(tex_com_corpo("Experiência com kubernetes"), config=config)


def test_tecnologia_do_inventario_nao_e_recusada_so_por_nome_parecido():
    inventario = _inventario("Docker Compose", "Python")
    config = configuracao_com(tecnologias_conhecidas=["Docker"])

    assert _regras(tex_minimo("Subi com Docker Compose."), inventario, config) == []
    assert _regras(tex_minimo("Subi com docker compose."), inventario, config) == []
    assert Regra.TECNOLOGIA in _regras(tex_minimo("Subi com Docker."), inventario, config)


def test_tecnologia_do_inventario_vence_a_lista_de_conhecidas():
    inventario = _inventario("Kubernetes")

    assert _regras(tex_minimo("Usei \\tech{Kubernetes} e kubernetes."), inventario) == []


def test_tecnologia_marcada_com_chaves_aninhadas_e_recusada():
    assert Regra.TECNOLOGIA in _regras(tex_com_corpo("Usei \\tech{Python{x}}."))


def test_marcador_sem_chaves_e_recusado():
    assert Regra.TECNOLOGIA in _regras(tex_com_corpo("Usei \\tech Python."))


def test_endereco_de_link_nao_conta_como_citacao_de_tecnologia():
    tex = tex_com_corpo("\\href{https://example.invalid/kafka-tools}{ver}")

    assert _regras(tex) == []


def test_lista_de_conhecidas_vem_da_configuracao():
    config = configuracao_com(tecnologias_conhecidas=["Cobol"])

    assert Regra.TECNOLOGIA in _regras(tex_com_corpo("Experiência com COBOL"), config=config)


def test_tecnologia_no_texto_do_pdf_e_recusada_em_qualquer_caixa(tmp_path):
    for texto in ("Kubernetes", "KUBERNETES", "kubernetes"):
        pdf = gravar_pdf(tmp_path, [f"Experiencia com {texto}"])

        resultado = validar_curriculo(tex_ficticio(), inventario_ficticio(), pdf=pdf)

        assert Regra.TECNOLOGIA in resultado.regras


def test_texto_do_pdf_com_tecnologia_do_inventario_passa(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Experiencia com Python e PostgreSQL"])

    assert validar_curriculo(tex_ficticio(), inventario_ficticio(), pdf=pdf).aprovado


FORMAS_LARGAS = [
    "\uff2b\uff55\uff42\uff45\uff52\uff4e\uff45\uff54\uff45\uff53",
    "\uff2b\uff21\uff26\uff2b\uff21",
]


@pytest.mark.parametrize("texto", FORMAS_LARGAS)
def test_tecnologia_em_forma_larga_e_reconhecida_apos_normalizar(texto):
    assert Regra.TECNOLOGIA in _regras(tex_com_corpo(f"Experiência com {texto}"))


@pytest.mark.parametrize("texto", FORMAS_LARGAS)
def test_tecnologia_em_forma_larga_no_pdf_e_reconhecida_apos_normalizar(texto):
    violacoes = validar_tecnologias_no_texto(
        f"Experiencia com {texto}", inventario_ficticio(), configuracao_validador()
    )

    assert [v.regra for v in violacoes] == [Regra.TECNOLOGIA]


def test_tecnologia_marcada_em_forma_larga_fora_do_inventario_e_recusada():
    assert Regra.TECNOLOGIA in _regras(tex_com_corpo("Usei \\tech{\uff2b\uff55\uff42\uff45}."))


def test_ligadura_do_pdf_e_normalizada_antes_de_comparar():
    inventario = _inventario("Flask")
    config = configuracao_com(tecnologias_conhecidas=["Fixtures"])

    achadas = validar_tecnologias_no_texto("usei \ufb01xtures", inventario, config)

    assert [v.regra for v in achadas] == [Regra.TECNOLOGIA]
