from __future__ import annotations

from copy import deepcopy

import pytest
from apoio_geracao import conteudo_ampliado, slots_ia_validos
from pydantic import ValidationError

from src.config import carregar
from src.gerador.configuracao import configuracao_gerador
from src.gerador.esquema import esquema_dos_slots

BLOCOS, _ = conteudo_ampliado()


def _config(**ajustes):
    dados = deepcopy(carregar("gerador"))
    for caminho, valor in ajustes.items():
        alvo = dados
        *pais, folha = caminho.split("__")
        for pai in pais:
            alvo = alvo[pai]
        alvo[folha] = valor
    return configuracao_gerador(dados)


def _validar(slots, config=None):
    config = config or configuracao_gerador()
    return esquema_dos_slots(config).model_validate(slots, strict=True)


def test_slots_validos_passam_no_esquema():
    assert _validar(slots_ia_validos(BLOCOS)).sobre.texto


def test_esquema_so_tem_os_slots_declarados_e_nunca_um_campo_de_latex():
    campos = set(esquema_dos_slots(configuracao_gerador()).model_fields)

    assert campos == set(configuracao_gerador().slots)
    assert not {"tex", "latex", "documento"} & campos


def test_json_schema_proibe_propriedade_extra_em_todo_objeto():
    esquema = esquema_dos_slots(configuracao_gerador()).model_json_schema()
    objetos = [esquema, *esquema["$defs"].values()]

    assert all(objeto["additionalProperties"] is False for objeto in objetos)


@pytest.mark.parametrize(
    "mutar",
    [
        lambda s: s.update(extra="x"),
        lambda s: s["sobre"].update(extra="x"),
        lambda s: s["experiencias"][0].update(extra="x"),
        lambda s: s["experiencias"][0]["bullets"][0].update(extra="x"),
        lambda s: s["projetos"][0].update(extra="x"),
        lambda s: s.pop("sobre"),
        lambda s: s["projetos"][0].pop("enfase"),
        lambda s: s["experiencias"][0]["bullets"][0].pop("techs"),
    ],
)
def test_campo_extra_ou_faltando_e_recusado(mutar):
    slots = slots_ia_validos(BLOCOS)
    mutar(slots)

    with pytest.raises(ValidationError):
        _validar(slots)


def test_tamanhos_vem_do_config_e_o_acima_do_limite_e_recusado():
    config = configuracao_gerador()
    sobre = config.slots["sobre"].max_chars
    bullet = config.slots["experiencias"].max_chars
    cheio = slots_ia_validos(BLOCOS)
    cheio["sobre"]["texto"] = "a" * sobre
    cheio["experiencias"][0]["bullets"][0]["texto"] = "a" * bullet
    _validar(cheio)

    sobre_demais = deepcopy(cheio)
    sobre_demais["sobre"]["texto"] = "a" * (sobre + 1)
    bullet_demais = deepcopy(cheio)
    bullet_demais["experiencias"][0]["bullets"][0]["texto"] = "a" * (bullet + 1)
    for slots in (sobre_demais, bullet_demais):
        with pytest.raises(ValidationError):
            _validar(slots)


def test_limite_apertado_no_yaml_vale_para_o_esquema():
    config = _config(slots__sobre__max_chars=10)
    slots = slots_ia_validos(BLOCOS)

    with pytest.raises(ValidationError):
        _validar(slots, config)


def _disciplinas_demais(slots, config):
    slots["disciplinas"] = ["a"] * (config.slots["disciplinas"].max_itens + 1)


def _disciplina_longa(slots, config):
    slots["disciplinas"] = ["a" * (config.slots["disciplinas"].max_chars + 1)]


def _experiencias_demais(slots, config):
    slots["experiencias"] *= config.slots["experiencias"].max_entradas + 1


def _bullets_demais(slots, config):
    entrada = slots["experiencias"][0]
    entrada["bullets"] *= config.slots["experiencias"].max_bullets + 1


def _bullets_vazios(slots, config):
    slots["experiencias"][0]["bullets"] = []


def _projetos_demais(slots, config):
    slots["projetos"] *= 2


def _projetos_de_menos(slots, config):
    slots["projetos"] = slots["projetos"][: config.ia.entradas_min["projeto"] - 1]


def _techs_demais(slots, config):
    slots["sobre"]["techs"] = ["x"] * (config.ia.techs_max + 1)


def _tech_longa(slots, config):
    slots["sobre"]["techs"] = ["x" * (config.ia.tech_max_chars + 1)]


def _enfase_demais(slots, config):
    slots["projetos"][0]["enfase"] = ["x"] * (config.ia.enfase_max + 1)


def _texto_vazio(slots, config):
    slots["sobre"]["texto"] = ""


def _id_fora_do_padrao(slots, config):
    slots["experiencias"][0]["bloco"] = "Exp-1; DROP"


@pytest.mark.parametrize(
    "mutar",
    [
        _disciplinas_demais,
        _disciplina_longa,
        _experiencias_demais,
        _bullets_demais,
        _bullets_vazios,
        _projetos_demais,
        _projetos_de_menos,
        _techs_demais,
        _tech_longa,
        _enfase_demais,
        _texto_vazio,
        _id_fora_do_padrao,
    ],
)
def test_lista_texto_ou_contagem_fora_do_limite_e_recusada(mutar):
    config = configuracao_gerador()
    slots = slots_ia_validos(BLOCOS)
    mutar(slots, config)

    with pytest.raises(ValidationError):
        _validar(slots)


def test_tipo_errado_nao_e_convertido_no_modo_estrito():
    slots = slots_ia_validos(BLOCOS)
    slots["experiencias"][0]["bullets"][0]["texto"] = 123

    with pytest.raises(ValidationError):
        _validar(slots)


@pytest.mark.parametrize(
    "ajuste",
    [
        {"sem_ia__entradas_por_tipo": {"projeto": 5}},
        {"sem_ia__entradas_por_tipo": {"projeto": 2}},
        {"sem_ia__bullets_por_tipo": {"experiencia": 3}},
        {"sem_ia__bullets_por_tipo": {"experiencia": 9, "projeto": 2}},
        {"ia__entradas_min": {"projeto": 9}},
        {"ia__tipos_com_enfase": ["sobre"]},
    ],
)
def test_config_incoerente_entre_ia_sem_ia_e_slots_e_recusada(ajuste):
    with pytest.raises(ValidationError):
        _config(**ajuste)
