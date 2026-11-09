from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from apoio_validador import configuracao_com

from src.avaliacao import calibracao
from src.avaliacao.configuracao import configuracao_avaliacao
from src.avaliacao.conjunto import Lote, carregar_entradas, conteudo_ficticio
from src.config import RAIZ
from src.validador.configuracao import configuracao_validador
from src.validador.resultado import Regra

AGORA = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
CONFIG_AVALIACAO = configuracao_avaliacao()
CONTEUDO = conteudo_ficticio(CONFIG_AVALIACAO)
ENTRADAS = tuple(carregar_entradas(RAIZ / CONFIG_AVALIACAO.armadilhas.pasta))
LOTES = [Lote(CONTEUDO, ENTRADAS, False)]


def _relatorio(config=None):
    return calibracao.calibrar(LOTES, config or configuracao_validador(), AGORA)


def test_relatorio_traz_falso_positivo_e_falso_negativo_por_regra_com_meta_da_configuracao():
    config = configuracao_validador()

    relatorio = _relatorio()

    regras = relatorio["regras"]
    assert set(config.calibracao.injecoes) <= {Regra(nome) for nome in regras}
    for dados in regras.values():
        assert dados["falso_positivo"]["meta"] == config.calibracao.metas.falso_positivo_max
        assert 0 <= dados["falso_positivo"]["taxa"] <= 1
        assert dados["falso_positivo"]["total"] == len(ENTRADAS)
    for regra in config.calibracao.injecoes:
        negativo = regras[regra.value]["falso_negativo"]
        assert negativo["total"] > 0
        assert negativo["meta"] == config.calibracao.metas.falso_negativo_max


def test_conjunto_da_f24_nao_tem_falso_positivo_nas_regras_do_conteudo():
    relatorio = _relatorio()

    assert {nome: d["falso_positivo"]["erros"] for nome, d in relatorio["regras"].items()} == {
        nome: 0 for nome in relatorio["regras"]
    }


def test_tecnologia_empresa_numero_e_copia_injetados_sao_pegos():
    relatorio = _relatorio()

    for regra in ("tecnologia", "empresa_da_vaga", "numero", "copia_da_vaga"):
        negativo = relatorio["regras"][regra]["falso_negativo"]
        assert negativo["erros"] == 0, regra


def test_meta_por_regra_da_configuracao_vale_no_relatorio():
    config = configuracao_com(
        calibracao__por_regra={"numero": {"falso_positivo_max": 0.5, "falso_negativo_max": 0.0}}
    )

    relatorio = _relatorio(config)

    assert relatorio["regras"]["numero"]["falso_negativo"]["meta"] == 0.0
    assert relatorio["regras"]["numero"]["falso_positivo"]["meta"] == 0.5
    assert relatorio["regras"]["tecnologia"]["falso_negativo"]["meta"] == 0.1


def test_regra_que_deixa_passar_a_injecao_aparece_como_falso_negativo_fora_da_meta(monkeypatch):
    monkeypatch.setattr(calibracao, "validar_conteudo", lambda tex, inv, contexto, config: [])

    relatorio = _relatorio()

    negativo = relatorio["regras"]["numero"]["falso_negativo"]
    assert negativo["erros"] == negativo["total"] > 0
    assert negativo["taxa"] == 1.0
    assert negativo["dentro_da_meta"] is False
    assert "numero" in relatorio["fora_da_meta"]
    assert relatorio["veredito"] == "fora_das_metas"


def test_regra_que_acusa_o_curriculo_bom_aparece_como_falso_positivo(monkeypatch):
    from src.validador.resultado import Violacao

    def sempre(tex, inventario, contexto, config):
        return [Violacao(Regra.PONTUACAO, "x")]

    monkeypatch.setattr(calibracao, "validar_conteudo", sempre)

    relatorio = _relatorio()

    positivo = relatorio["regras"]["pontuacao"]["falso_positivo"]
    assert positivo["erros"] == positivo["total"]
    assert positivo["dentro_da_meta"] is False
    assert "pontuacao" in relatorio["fora_da_meta"]


def test_termo_ignorado_pela_configuracao_sai_da_conta_de_falso_negativo():
    base = configuracao_validador()
    sem_ignorar = configuracao_com(
        calibracao__injecoes={
            regra.value: {**injecao.model_dump(mode="json"), "ignorar": []}
            for regra, injecao in base.calibracao.injecoes.items()
        }
    )

    com = _relatorio()["regras"]["senioridade"]["falso_negativo"]["total"]
    sem = _relatorio(sem_ignorar)["regras"]["senioridade"]["falso_negativo"]["total"]

    assert sem == com + 1


def test_indicio_conta_como_regra_que_pegou():
    relatorio = _relatorio()

    assert relatorio["regras"]["copia_da_vaga"]["falso_negativo"]["erros"] == 0


def test_relatorio_nao_carrega_texto_de_vaga_nem_trecho_do_curriculo():
    texto = json.dumps(_relatorio(), ensure_ascii=False)

    for entrada in ENTRADAS:
        assert entrada.texto[:40] not in texto
    assert "\\section" not in texto


def test_gravar_relatorio_vai_para_dados_com_permissao_restrita(tmp_path):
    caminho = calibracao.gravar(_relatorio(), tmp_path, configuracao_validador(), AGORA)

    assert caminho.resolve().is_relative_to(tmp_path.resolve())
    assert caminho.stat().st_mode & 0o777 == 0o600
    assert json.loads(caminho.read_text(encoding="utf-8"))["veredito"]


def test_gravar_relatorio_fora_de_dados_e_recusado(tmp_path):
    config = configuracao_com(calibracao__subpasta="../fora")

    with pytest.raises(calibracao.RelatorioForaDeDados):
        calibracao.gravar(_relatorio(), tmp_path, config, AGORA)


def test_comando_sai_com_zero_dentro_das_metas_e_um_fora(tmp_path, capsys):
    assert calibracao.executar(tmp_path) in (0, 1)
    assert "falso" in capsys.readouterr().out


def _anuncio(config):
    entrada = next(e for e in ENTRADAS if e.tipo == "prompt_injection")
    return calibracao._termos_anuncio(entrada, CONTEUDO, config)[0]


def test_palavras_extras_do_trecho_do_anuncio_vem_da_configuracao():
    base = configuracao_validador()
    mais = configuracao_com(calibracao__palavras_extras_do_anuncio=5)
    esperado = base.conteudo.copia_da_vaga.palavras + base.calibracao.palavras_extras_do_anuncio

    palavras_base = len(_anuncio(base).split())
    palavras_mais = len(_anuncio(mais).split())

    assert palavras_base == esperado
    assert palavras_mais - palavras_base == 3


def test_caracteres_fora_do_texto_vem_da_configuracao():
    config = configuracao_com(calibracao__caracteres_fora_do_texto="[^a-z ]")

    trecho = _anuncio(config)

    assert set(trecho) <= set("abcdefghijklmnopqrstuvwxyz ")
