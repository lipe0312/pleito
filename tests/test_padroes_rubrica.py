from __future__ import annotations

import copy

import pytest

from src.config import carregar
from src.gerador.slots import TextoComTechs
from src.padroes.configuracao import configuracao_padroes
from src.padroes.erros import FamiliaDesconhecida, IdiomaDesconhecido
from src.padroes.rubrica import CurriculoAvaliado, avaliar

FAMILIA = "backend_arquitetura"
TECHS_PEDIDAS = ["Python", "PostgreSQL", "Docker"]
INVENTARIO = ["Python", "PostgreSQL", "Docker"]


def _item(texto: str, *techs: str) -> TextoComTechs:
    return TextoComTechs(texto=texto, techs=list(techs))


SOBRE_BOM = _item(
    "Desenvolvedor backend focado em APIs REST e dados relacionais, com experiência em "
    "microsserviços de gestão de estoque para empresas fictícias, usando Python e PostgreSQL "
    "em ambientes conteinerizados, com testes automatizados e documentação de contratos de API "
    "mantida junto do código.",
    "Python",
    "PostgreSQL",
)

CURRICULO_BOM = CurriculoAvaliado(
    sobre=SOBRE_BOM,
    bullets_por_entrada=[
        [
            _item(
                "Construí uma API de cadastro de produtos com Python e PostgreSQL para o "
                "estoque da Acme Fictícia.",
                "Python",
                "PostgreSQL",
            ),
            _item(
                "Implementei a execução local dos serviços com Docker Compose e testes "
                "automatizados de integração.",
                "Docker",
            ),
            _item(
                "Otimizei consultas de relatório com índices e views materializadas no "
                "PostgreSQL, reduzindo a espera nas telas internas.",
                "PostgreSQL",
            ),
        ],
        [
            _item(
                "Projetei um serviço de fila de pedidos em Python com contratos de API "
                "documentados e versionados.",
                "Python",
            ),
            _item(
                "Automatizei a publicação das imagens de contêiner com Docker em um "
                "pipeline de integração contínua.",
                "Docker",
            ),
        ],
    ],
)

CURRICULO_RUIM = CurriculoAvaliado(
    sobre=_item("Profissional proativo e dinâmico, apaixonado por tecnologia."),
    bullets_por_entrada=[
        [
            _item("Liderei a equipe do zero em diversas tarefas."),
            _item("Liderei diversas atividades do time."),
            _item("Responsável por várias coisas, etc."),
        ]
    ],
)


def _config():
    return configuracao_padroes()


def _nota(
    curriculo, techs=TECHS_PEDIDAS, familia=FAMILIA, idioma="pt", config=None, inventario=INVENTARIO
):
    return avaliar(config or _config(), curriculo, idioma, familia, techs, inventario)


def test_curriculo_ficticio_bom_passa_da_nota_minima():
    nota = _nota(CURRICULO_BOM)
    assert nota.aprovado
    assert nota.total >= _config().rubrica.nota_minima


def test_curriculo_ficticio_ruim_fica_abaixo_da_nota_minima():
    nota = _nota(CURRICULO_RUIM)
    assert not nota.aprovado
    assert nota.total < _config().rubrica.nota_minima


def test_bullet_com_verbo_proibido_e_sem_tecnologia_pontua_abaixo_do_minimo():
    curriculo = CurriculoAvaliado(
        sobre=SOBRE_BOM,
        bullets_por_entrada=[[_item("Liderei o time do zero.")]],
    )
    nota = _nota(curriculo)
    assert nota.notas["bullet_vago"] == 0
    assert nota.total < _config().rubrica.nota_minima


def test_sem_a_regra_de_senioridade_o_bullet_so_com_verbo_proibido_passaria():
    bruto = copy.deepcopy(carregar("padroes_curriculo"))
    bruto["senioridade_inflada"] = {
        "verbos": {"pt": ["inexistente"], "en": ["inexistente"]},
        "expressoes": {"pt": ["inexistente"], "en": ["inexistente"]},
    }
    texto = (
        "Liderei a migração de um serviço fictício de pedidos para Python com PostgreSQL e "
        "testes automatizados de regressão."
    )
    curriculo = CurriculoAvaliado(
        sobre=SOBRE_BOM,
        bullets_por_entrada=[[_item(texto, "Python", "PostgreSQL")]],
    )
    com_regra = _nota(curriculo)
    sem_regra = _nota(curriculo, config=configuracao_padroes(bruto))
    assert com_regra.notas["bullet_vago"] == 0
    assert sem_regra.notas["bullet_vago"] == 1


def test_cobertura_conta_so_as_techs_pedidas_citadas():
    inventario = [*INVENTARIO, "Kubernetes"]
    cobertura = _nota(
        CURRICULO_BOM, techs=["Python", "Kubernetes"], inventario=inventario
    ).notas["cobertura_techs"]
    assert cobertura == 0.5


def test_cobertura_ignora_caixa():
    curriculo = CurriculoAvaliado(sobre=_item("x", "PYTHON"), bullets_por_entrada=[])
    assert _nota(curriculo, techs=["python"]).notas["cobertura_techs"] == 1


def test_vaga_sem_techs_pedidas_nao_penaliza_cobertura():
    assert _nota(CURRICULO_BOM, techs=[]).notas["cobertura_techs"] == 1


def test_verbo_repetido_na_mesma_entrada_derruba_a_nota():
    repetido = CurriculoAvaliado(
        sobre=SOBRE_BOM,
        bullets_por_entrada=[
            [
                _item("Construí uma API com Python e PostgreSQL para o estoque.", "Python"),
                _item("Construí uma fila de pedidos com Python e Docker em contêiner.", "Python"),
            ]
        ],
    )
    assert _nota(repetido).notas["verbo_repetido"] == 0.5
    assert _nota(CURRICULO_BOM).notas["verbo_repetido"] == 1


def test_mesmo_verbo_em_entradas_diferentes_nao_conta_como_repetido():
    curriculo = CurriculoAvaliado(
        sobre=SOBRE_BOM,
        bullets_por_entrada=[
            [_item("Construí uma API com Python e PostgreSQL para o estoque.", "Python")],
            [_item("Construí uma fila de pedidos com Python e Docker em contêiner.", "Python")],
        ],
    )
    assert _nota(curriculo).notas["verbo_repetido"] == 1


def test_aderencia_usa_o_foco_da_familia_e_do_idioma():
    assert _nota(CURRICULO_BOM).notas["aderencia_familia"] == 1
    assert _nota(CURRICULO_BOM, familia="iot_embarcados_visao").notas["aderencia_familia"] == 0
    en = CurriculoAvaliado(
        sobre=_item("Backend developer focused on APIs and relational data.", "Python"),
        bullets_por_entrada=[],
    )
    assert _nota(en, idioma="en").notas["aderencia_familia"] == 1


def test_sobre_com_frase_vazia_sem_tech_e_curto_zera_a_nota_do_sobre():
    assert _nota(CURRICULO_RUIM).notas["sobre_generico"] == 0
    assert _nota(CURRICULO_BOM).notas["sobre_generico"] == 1


def test_bullet_fora_da_faixa_de_techs_ou_tamanho_e_vago():
    sem_tech = _item("Construí uma API de cadastro de produtos para o estoque da Acme Fictícia.")
    curto = _item("Construí API.", "Python")
    curriculo = CurriculoAvaliado(sobre=SOBRE_BOM, bullets_por_entrada=[[sem_tech, curto]])
    assert _nota(curriculo).notas["bullet_vago"] == 0


def test_curriculo_sem_bullets_nao_aprova():
    vazio = CurriculoAvaliado(sobre=SOBRE_BOM, bullets_por_entrada=[])
    nota = _nota(vazio)
    assert nota.notas["bullet_vago"] == 0
    assert nota.notas["verbo_repetido"] == 0


def test_familia_ou_idioma_desconhecido_e_recusado():
    with pytest.raises(FamiliaDesconhecida, match="inexistente"):
        _nota(CURRICULO_BOM, familia="inexistente")
    with pytest.raises(IdiomaDesconhecido, match="fr"):
        _nota(CURRICULO_BOM, idioma="fr")


def test_total_e_a_soma_ponderada_dos_criterios():
    config = _config()
    nota = _nota(CURRICULO_BOM)
    esperado = sum(
        config.rubrica.criterios[nome].peso * valor for nome, valor in nota.notas.items()
    )
    assert nota.total == pytest.approx(esperado)


def _nota_do_bullet_unico(texto: str, *techs: str, idioma: str = "pt") -> float:
    curriculo = CurriculoAvaliado(
        sobre=SOBRE_BOM, bullets_por_entrada=[[_item(texto, *techs)]]
    )
    return _nota(curriculo, idioma=idioma).notas["bullet_vago"]


BULLET_CONCRETO = "Construí uma API de cadastro de produtos com Python e PostgreSQL para a Acme."


def test_termo_vago_derruba_o_bullet_e_sem_ele_o_bullet_passa():
    assert _nota_do_bullet_unico(BULLET_CONCRETO, "Python", "PostgreSQL") == 1
    vago = BULLET_CONCRETO.replace("uma API", "diversas APIs")
    assert _nota_do_bullet_unico(vago, "Python", "PostgreSQL") == 0


def test_abertura_vaga_derruba_o_bullet():
    texto = "Responsável por uma API de cadastro de produtos com Python e PostgreSQL na Acme."
    assert _nota_do_bullet_unico(texto, "Python", "PostgreSQL") == 0


def test_listas_em_ingles_valem_para_o_idioma_en():
    ok = "Built a product registration API with Python and PostgreSQL for a fictional Acme."
    assert _nota_do_bullet_unico(ok, "Python", "PostgreSQL", idioma="en") == 1
    inflado = ok.replace("Built", "Led")
    assert _nota_do_bullet_unico(inflado, "Python", "PostgreSQL", idioma="en") == 0
    assert _nota_do_bullet_unico(inflado, "Python", "PostgreSQL", idioma="pt") == 1


def test_tech_pedida_e_citada_mas_fora_do_inventario_nao_sobe_a_cobertura():
    curriculo = CurriculoAvaliado(
        sobre=_item("x", "Kubernetes"),
        bullets_por_entrada=[[_item("Construí algo com Kubernetes.", "Kubernetes")]],
    )
    pedidas = ["Python", "Kubernetes"]
    sem_inventario = _nota(curriculo, techs=pedidas).notas["cobertura_techs"]
    com_inventario = _nota(
        curriculo, techs=pedidas, inventario=[*INVENTARIO, "Kubernetes"]
    ).notas["cobertura_techs"]
    assert sem_inventario == 0
    assert com_inventario == 0.5


def test_pedida_fora_do_inventario_sai_do_calculo_em_vez_de_penalizar():
    curriculo = CurriculoAvaliado(sobre=_item("x", "Python"), bullets_por_entrada=[])
    nota = _nota(curriculo, techs=["Python", "Kubernetes"])
    assert nota.notas["cobertura_techs"] == 1


def test_vaga_so_com_techs_fora_do_inventario_nao_penaliza_cobertura():
    assert _nota(CURRICULO_BOM, techs=["Kubernetes"]).notas["cobertura_techs"] == 1
