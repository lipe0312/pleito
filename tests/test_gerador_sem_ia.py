from __future__ import annotations

import pytest
from apoio_geracao import EMAIL, FAMILIAS, IDIOMAS, TELEFONE, VAGA, conteudo_ampliado
from apoio_gerador import conteudo_ficticio, travado_ficticio

from src.gerador.configuracao import configuracao_gerador
from src.gerador.gerar import ModoGeracao, gerar_curriculo, gerar_sem_ia
from src.padroes.configuracao import configuracao_padroes
from src.padroes.erros import FamiliaDesconhecida, IdiomaDesconhecido
from src.validador.resultado import CurriculoInvalido, Regra
from src.validador.validar import validar_fonte

BLOCOS, INVENTARIO = conteudo_ampliado()
TRAVADO = travado_ficticio()


def _gerar(
    familia="backend_arquitetura", idioma="pt", vaga=VAGA, blocos=BLOCOS, inventario=INVENTARIO
):
    return gerar_sem_ia(familia, idioma, vaga, blocos, inventario, TRAVADO)


def _ids(resultado, nome):
    return [entrada["bloco"] for entrada in resultado.slots[nome]]


@pytest.mark.parametrize("familia", FAMILIAS)
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_as_quatro_familias_em_pt_e_en_geram_fonte_aprovada_pelo_validador(familia, idioma):
    resultado = _gerar(familia, idioma, vaga="")

    assert resultado.modo is ModoGeracao.SEM_IA
    assert validar_fonte(resultado.tex, INVENTARIO).aprovado
    assert EMAIL in resultado.tex
    assert TELEFONE in resultado.tex


def test_mesma_entrada_gera_exatamente_o_mesmo_tex():
    assert _gerar().tex == _gerar().tex


def test_familia_muda_os_projetos_escolhidos():
    backend = _ids(_gerar("backend_arquitetura", vaga=""), "projetos")
    frontend = _ids(_gerar("fullstack_frontend", vaga=""), "projetos")
    dados = _ids(_gerar("dados_ml_ia", vaga=""), "projetos")

    assert backend[0] == "proj_projeto_alfa_beta"
    assert frontend[0] == "proj_gama"
    assert dados[0] == "proj_delta"


def test_familia_muda_a_ordem_dos_bullets_da_experiencia():
    backend = _gerar("backend_arquitetura", vaga="").slots["experiencias"][0]["bullets"]
    iot = _gerar("iot_embarcados_visao", vaga="").slots["experiencias"][0]["bullets"]

    assert backend[0]["texto"].startswith("Construí")
    assert iot[0]["texto"].startswith("Mantive")


def test_tech_da_vaga_puxa_o_projeto_que_a_usa():
    sem_vaga = _ids(_gerar("backend_arquitetura", vaga=""), "projetos")
    com_vaga = _ids(_gerar("backend_arquitetura", vaga="Pede MQTT, RabbitMQ e Pandas."), "projetos")

    assert sem_vaga == ["proj_projeto_alfa_beta", "proj_gama", "proj_delta"]
    assert com_vaga == ["proj_projeto_alfa_beta", "proj_epsilon", "proj_delta"]


def test_tech_da_vaga_vira_enfase_do_projeto_escolhido():
    resultado = _gerar("backend_arquitetura", vaga="Experiência com React e TypeScript.")

    assert resultado.enfase["proj_gama"] == ("React", "TypeScript")


def test_texto_da_vaga_nao_entra_no_tex():
    resultado = _gerar(vaga="Acme Ficticia pede Python. Segredo-da-vaga-123.")

    assert "Segredo-da-vaga-123" not in resultado.tex
    assert "Acme" not in resultado.tex


def test_experiencias_ficam_todas_na_ordem_dos_blocos():
    resultado = _gerar()

    assert _ids(resultado, "experiencias") == [
        "exp_empresa_exemplo_ltda",
        "exp_laboratorio_exemplo_visao",
    ]


def test_limites_do_config_sao_respeitados():
    config = configuracao_gerador()
    resultado = _gerar()

    assert len(resultado.slots["projetos"]) == config.sem_ia.entradas_por_tipo["projeto"]
    for entrada in resultado.slots["projetos"]:
        assert len(entrada["bullets"]) <= config.sem_ia.bullets_por_tipo["projeto"]
    for entrada in resultado.slots["experiencias"]:
        assert len(entrada["bullets"]) <= config.sem_ia.bullets_por_tipo["experiencia"]


def test_sem_blocos_o_bastante_usa_o_que_existe():
    blocos, inventario = conteudo_ficticio()

    resultado = _gerar(blocos=blocos, inventario=inventario)

    assert _ids(resultado, "projetos") == ["proj_projeto_alfa_beta"]
    assert validar_fonte(resultado.tex, inventario).aprovado


def test_blocos_que_geram_fonte_invalida_nao_viram_tex_no_modo_sem_ia():
    redacao_invalida = {i: "Orquestrei com Kubernetes." for i in IDIOMAS}
    invalidos = BLOCOS.model_copy(
        update={
            "blocos": [
                bloco.model_copy(
                    update={
                        "bullets": [
                            b.model_copy(update={"redacao": redacao_invalida})
                            for b in bloco.bullets
                        ]
                    }
                )
                for bloco in BLOCOS.blocos
            ]
        }
    )

    with pytest.raises(CurriculoInvalido) as erro:
        _gerar(blocos=invalidos)

    assert Regra.TECNOLOGIA in erro.value.resultado.regras


def test_nao_ha_chamada_nem_prompt_no_modo_sem_ia():
    resultado = _gerar()

    assert resultado.prompt_versao is None
    assert resultado.prompt_sha256 is None
    assert resultado.motivo is None


def test_familia_ou_idioma_desconhecido_e_recusado():
    with pytest.raises(FamiliaDesconhecida):
        _gerar("familia_inventada")
    with pytest.raises(IdiomaDesconhecido):
        _gerar(idioma="fr")


def test_sem_roteador_o_gerar_cai_no_modo_sem_ia():
    resultado = gerar_curriculo(
        "backend_arquitetura", "pt", VAGA, BLOCOS, INVENTARIO, TRAVADO, roteador=None
    )

    assert resultado.modo is ModoGeracao.SEM_IA
    assert resultado.tex == _gerar().tex


def test_padroes_e_gerador_declaram_as_mesmas_familias():
    assert set(configuracao_padroes().foco_sobre) == set(FAMILIAS)
