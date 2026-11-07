from __future__ import annotations

from datetime import UTC, datetime

from src.avaliacao import execucao
from src.avaliacao.configuracao import configuracao_avaliacao
from src.avaliacao.conjunto import Lote, carregar_entradas, conteudo_ficticio
from src.avaliacao.referencia import resposta_de_referencia, transporte_fixo
from src.avaliacao.runner import avaliar
from src.config import RAIZ, carregar
from src.gerador.configuracao import configuracao_gerador
from src.validador.resultado import Nivel, Regra, Violacao

AGORA = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
CONFIG = configuracao_avaliacao()
CONTEUDO = conteudo_ficticio(CONFIG)
ARMADILHAS = carregar_entradas(RAIZ / CONFIG.armadilhas.pasta)


def _referencia(entrada, conteudo):
    resposta = resposta_de_referencia(conteudo, entrada.idioma, configuracao_gerador())
    return transporte_fixo(resposta, 100, 50)


def _avaliar():
    lotes = [Lote(CONTEUDO, tuple(ARMADILHAS), False)]
    return avaliar("forte", lotes, CONFIG, carregar("modelos"), AGORA, _referencia)


def _validador_que_devolve(*violacoes):
    return lambda tex, inventario, contexto, config=None: list(violacoes)


def test_indicio_e_salvo_do_validador_nao_reprovam_o_tier(monkeypatch):
    achados = [
        Violacao(Regra.COPIA_DA_VAGA, "x", nivel=Nivel.INDICIO),
        Violacao(Regra.TECNOLOGIA, "y", nivel=Nivel.OK),
    ]
    monkeypatch.setattr(execucao, "validar_conteudo", _validador_que_devolve(*achados))

    relatorio = _avaliar()

    assert relatorio["veredito"] == "aprovado", relatorio["motivos"]
    assert relatorio["taxa_aprovacao"] == 1.0


def test_bloqueia_do_validador_reprova_o_tier_e_conta_na_regra(monkeypatch):
    achados = [
        Violacao(Regra.COPIA_DA_VAGA, "x", nivel=Nivel.INDICIO),
        Violacao(Regra.NUMERO, "y"),
    ]
    monkeypatch.setattr(execucao, "validar_conteudo", _validador_que_devolve(*achados))

    relatorio = _avaliar()

    assert relatorio["veredito"] == "reprovado"
    assert relatorio["taxa_por_regra"]["numero"] < 1.0
    assert relatorio["taxa_por_regra"]["copia_da_vaga"] == 1.0
