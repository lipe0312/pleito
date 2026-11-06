from __future__ import annotations

import re
from copy import deepcopy

import httpx
import pytest
from apoio_geracao import (
    EMAIL,
    INJECAO,
    TELEFONE,
    VAGA,
    conteudo_ampliado,
    roteador_falso,
    slots_ia_validos,
)
from apoio_gerador import travado_ficticio

from src.db.flags import SistemaDesativado
from src.gerador.erros import RespostaDescartada
from src.gerador.gerar import ModoGeracao, MotivoSemIa, gerar_curriculo
from src.llm.orcamento import OrcamentoEsgotado, SaldoInsuficienteTierForte
from src.padroes.configuracao import configuracao_padroes
from src.validador.resultado import CurriculoInvalido, Regra
from src.validador.validar import validar_fonte

BLOCOS, INVENTARIO = conteudo_ampliado()
TRAVADO = travado_ficticio()
FAMILIA = "backend_arquitetura"


def _gerar(roteador, vaga=VAGA, idioma="pt"):
    return gerar_curriculo(FAMILIA, idioma, vaga, BLOCOS, INVENTARIO, TRAVADO, roteador)


def _validos(idioma="pt"):
    return slots_ia_validos(BLOCOS, idioma)


def _descartar(slots):
    roteador, rastro = roteador_falso(slots)
    with pytest.raises(RespostaDescartada):
        _gerar(roteador)
    return rastro


def test_resposta_valida_vira_tex_aprovado_pelo_validador():
    roteador, rastro = roteador_falso(_validos())

    resultado = _gerar(roteador)

    assert resultado.modo is ModoGeracao.IA
    assert validar_fonte(resultado.tex, INVENTARIO).aprovado
    assert r"\tech{Python}" in resultado.tex
    assert len(rastro.pedidos) == 1


def test_chamada_usa_tarefa_e_tier_do_config_com_orcamento_reservado_e_finalizado():
    roteador, rastro = roteador_falso(_validos())

    _gerar(roteador)

    assert rastro.reservas[0]["etapa"] == "escrita_slots"
    assert rastro.reservas[0]["tier"] == "forte"
    assert rastro.reservas[0]["custo_maximo_usd"] > 0
    assert len(rastro.finalizacoes) == 1
    assert rastro.finalizacoes[0][-1] == "valida"


def test_pedido_nao_leva_ferramenta_e_exige_json_estrito():
    roteador, rastro = roteador_falso(_validos())

    _gerar(roteador)

    pedido = rastro.pedidos[0]
    assert "tools" not in pedido
    assert pedido["text"]["format"]["strict"] is True
    assert pedido["store"] is False


def test_prompt_e_o_do_f3_0_com_vaga_so_dentro_da_marcacao_de_dado_nao_confiavel():
    roteador, rastro = roteador_falso(_validos())
    padroes = configuracao_padroes()

    resultado = _gerar(roteador, vaga=f"{VAGA}\n{INJECAO}")

    prompt = rastro.pedidos[0]["input"]
    abre = prompt.rindex(padroes.marcacao.abre)
    fecha = prompt.rindex(padroes.marcacao.fecha)
    assert abre < prompt.index(INJECAO) < fecha
    assert prompt.count(INJECAO) == 1
    assert resultado.prompt_versao >= 1
    assert re.fullmatch(r"[0-9a-f]{64}", resultado.prompt_sha256)
    assert str(resultado.prompt_versao) in rastro.reservas[0]["prompt_versao"]


def test_prompt_nao_leva_telefone_nem_email():
    roteador, rastro = roteador_falso(_validos())

    _gerar(roteador)

    prompt = rastro.pedidos[0]["input"]
    assert EMAIL not in prompt
    assert TELEFONE not in prompt
    assert "@" not in prompt


def test_bullet_com_id_inventado_e_descartado():
    slots = _validos()
    slots["experiencias"][0]["bullets"][0]["id"] = "bullet_que_nao_existe"

    rastro = _descartar(slots)

    assert rastro.finalizacoes[0][-1] == "valida"


def test_bullet_de_outro_bloco_e_descartado():
    slots = _validos()
    slots["experiencias"][0]["bullets"][0]["id"] = "exp_laboratorio_exemplo_visao_1"

    _descartar(slots)


def test_bloco_inventado_ou_de_outro_tipo_e_descartado():
    inventado = _validos()
    inventado["projetos"][0]["bloco"] = "proj_que_nao_existe"
    de_outro_tipo = _validos()
    de_outro_tipo["projetos"][0]["bloco"] = "exp_empresa_exemplo_ltda"

    _descartar(inventado)
    _descartar(de_outro_tipo)


def test_bloco_repetido_e_descartado():
    slots = _validos()
    slots["projetos"][1] = deepcopy(slots["projetos"][0])

    _descartar(slots)


def test_bullet_repetido_na_mesma_entrada_e_descartado():
    slots = _validos()
    entrada = slots["experiencias"][0]
    entrada["bullets"] = [entrada["bullets"][0], entrada["bullets"][0]]

    _descartar(slots)


def test_experiencia_omitida_ou_fora_da_ordem_dos_blocos_e_descartada():
    omitida = _validos()
    omitida["experiencias"] = omitida["experiencias"][:1]
    trocada = _validos()
    trocada["experiencias"].reverse()

    _descartar(omitida)
    _descartar(trocada)


def test_campo_extra_e_descartado():
    slots = _validos()
    slots["tex"] = r"\documentclass{article}"

    _descartar(slots)


def test_campo_extra_dentro_do_bullet_e_descartado():
    slots = _validos()
    slots["experiencias"][0]["bullets"][0]["comando"] = "rodar"

    rastro = _descartar(slots)

    assert rastro.finalizacoes[0][-1] == "invalida"


def test_tamanho_acima_do_limite_e_descartado():
    slots = _validos()
    slots["sobre"]["texto"] = "a" * 701

    rastro = _descartar(slots)

    assert rastro.finalizacoes[0][-1] == "invalida"


def test_json_quebrado_e_descartado():
    roteador, _ = roteador_falso("{nao e json")

    with pytest.raises(RespostaDescartada):
        _gerar(roteador)


def test_texto_inteiro_de_latex_no_lugar_do_json_e_descartado():
    roteador, _ = roteador_falso(r"\documentclass{article}\begin{document}x\end{document}")

    with pytest.raises(RespostaDescartada):
        _gerar(roteador)


def test_tech_fora_do_inventario_e_descartada():
    slots = _validos()
    slots["experiencias"][0]["bullets"][0]["techs"] = ["Kubernetes"]

    _descartar(slots)


def test_enfase_fora_do_inventario_ou_alheia_ao_projeto_e_descartada():
    fora = _validos()
    fora["projetos"][0]["enfase"] = ["Kubernetes"]
    alheia = _validos()
    alheia["projetos"][0]["enfase"] = ["RabbitMQ"]

    _descartar(fora)
    _descartar(alheia)


def test_disciplina_fora_do_inventario_e_descartada():
    slots = _validos()
    slots["disciplinas"] = ["Disciplina Inventada"]

    _descartar(slots)


def test_injecao_pedindo_input_nao_produz_latex_fora_do_escape():
    slots = _validos()
    slots["sobre"]["texto"] = r"\input{/etc/passwd} e \write18{touch /tmp/x}"
    for entrada in slots["experiencias"] + slots["projetos"]:
        entrada["bullets"][0]["texto"] = r"\input{/etc/passwd} $x$ & % #"
    roteador, _ = roteador_falso(slots)

    resultado = _gerar(roteador, vaga=f"{VAGA}\n{INJECAO}")

    assert not re.search(r"\\input|\\write|\\include|\\immediate", resultado.tex)
    assert r"\textbackslash{}input\{/etc/passwd\}" in resultado.tex
    assert validar_fonte(resultado.tex, INVENTARIO).aprovado


def test_injecao_no_nome_da_tecnologia_e_descartada():
    slots = _validos()
    slots["sobre"]["techs"] = [r"Python}\input{/etc/passwd}\tech{x"]

    _descartar(slots)


def test_texto_que_o_validador_recusa_nao_vira_tex():
    slots = _validos()
    slots["sobre"]["texto"] = "Orquestrei servicos com Kubernetes em producao."
    roteador, _ = roteador_falso(slots)

    with pytest.raises(CurriculoInvalido) as erro:
        _gerar(roteador)

    assert "Kubernetes" in str(erro.value)
    assert not isinstance(erro.value, RespostaDescartada)
    assert Regra.TECNOLOGIA in erro.value.resultado.regras


def test_tier_desligado_gera_sem_ia_e_o_uso_llm_fica_vazio():
    roteador, rastro = roteador_falso(_validos(), habilitado=False)

    resultado = _gerar(roteador)

    assert resultado.modo is ModoGeracao.SEM_IA
    assert resultado.motivo is MotivoSemIa.MODELO_INDISPONIVEL
    assert rastro.reservas == []
    assert rastro.finalizacoes == []
    assert rastro.falhas == []
    assert rastro.pedidos == []
    assert validar_fonte(resultado.tex, INVENTARIO).aprovado


@pytest.mark.parametrize("erro", [OrcamentoEsgotado, SaldoInsuficienteTierForte])
def test_sem_orcamento_gera_sem_ia_e_nada_e_enviado(erro):
    def sem_saldo():
        raise erro("sem saldo")

    roteador, rastro = roteador_falso(_validos(), reserva=sem_saldo)

    resultado = _gerar(roteador)

    assert resultado.modo is ModoGeracao.SEM_IA
    assert resultado.motivo is MotivoSemIa.SEM_ORCAMENTO
    assert rastro.reservas == []
    assert rastro.pedidos == []


def test_sistema_desativado_para_tudo_em_vez_de_cair_no_sem_ia():
    def desativado():
        raise SistemaDesativado("flag")

    roteador, rastro = roteador_falso(_validos(), ativo=desativado)

    with pytest.raises(SistemaDesativado):
        _gerar(roteador)

    assert rastro.pedidos == []


def test_falha_de_rede_propaga_para_quem_decide_a_tentativa():
    roteador, rastro = roteador_falso(_validos())

    def cair(pedido):
        raise httpx.ConnectError("sem rede")

    roteador.transporte = cair

    with pytest.raises(httpx.ConnectError):
        _gerar(roteador)

    assert len(rastro.falhas) == 1


def test_resultado_em_en_usa_os_blocos_em_ingles():
    roteador, _ = roteador_falso(_validos("en"))

    resultado = _gerar(roteador, idioma="en")

    assert "Built an API" in resultado.tex
    assert r"\section{About}" in resultado.tex
