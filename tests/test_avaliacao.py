from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.avaliacao import __main__ as cli
from src.avaliacao.configuracao import configuracao_avaliacao
from src.avaliacao.conjunto import Lote, carregar_entradas, conteudo_ficticio
from src.avaliacao.execucao import EXECUTORES, termos_proibidos
from src.avaliacao.referencia import resposta_de_referencia, transporte_fixo
from src.avaliacao.relatorio import gravar_relatorio
from src.avaliacao.runner import avaliar
from src.config import RAIZ, carregar
from src.gerador.configuracao import configuracao_gerador
from src.llm.roteador import ModeloIndisponivel

AGORA = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
CONFIG = configuracao_avaliacao()
CONTEUDO = conteudo_ficticio(CONFIG)
ARMADILHAS = carregar_entradas(RAIZ / CONFIG.armadilhas.pasta)
CAMPOS_DO_RELATORIO = {
    "data",
    "tier",
    "modo",
    "provedor",
    "modelo",
    "versao_conjunto",
    "versoes_prompt",
    "execucoes",
    "taxa_aprovacao",
    "taxa_por_regra",
    "falhas_por_armadilha",
    "armadilhas",
    "armadilhas_sem_cobertura",
    "vagas_reais",
    "custo_usd",
    "chamadas",
    "veredito",
    "motivos",
}


def _referencia(entrada, conteudo):
    return transporte_fixo(
        resposta_de_referencia(conteudo, entrada.idioma, configuracao_gerador()), 100, 50
    )


def _obediente(alterar):
    def fabrica(entrada, conteudo):
        resposta = resposta_de_referencia(conteudo, entrada.idioma, configuracao_gerador())
        if entrada.tipo == "prompt_injection":
            alterar(resposta, entrada)
        return transporte_fixo(resposta, 100, 50)

    return fabrica


def _avaliar(fabrica, config=CONFIG, lotes=None, tier="forte"):
    lotes = lotes if lotes is not None else [Lote(CONTEUDO, tuple(ARMADILHAS), False)]
    return avaliar(tier, lotes, config, carregar("modelos"), AGORA, fabrica)


def _armadilha(relatorio, tipo):
    return next(item for item in relatorio["armadilhas"] if item["tipo"] == tipo)


def test_cliente_correto_aprova_o_tier_e_o_relatorio_tem_todos_os_campos(tmp_path):
    relatorio = _avaliar(_referencia)

    assert relatorio["veredito"] == "aprovado", relatorio["motivos"]
    assert CAMPOS_DO_RELATORIO <= set(relatorio)
    assert relatorio["modo"] == "offline"
    assert relatorio["modelo"] == carregar("modelos")["tiers"]["forte"]["modelo"]
    assert relatorio["versao_conjunto"].startswith(f"v{CONFIG.versao_conjunto}-")
    assert relatorio["versoes_prompt"] == {"escrita_slots": ["gerar_slots_v1"]}
    assert relatorio["taxa_aprovacao"] == 1.0
    assert set(relatorio["taxa_por_regra"].values()) == {1.0}
    assert "paginas" not in relatorio["taxa_por_regra"]
    assert relatorio["falhas_por_armadilha"] == {}
    assert relatorio["chamadas"] == len(ARMADILHAS)
    assert Decimal(relatorio["custo_usd"]) > 0

    caminho = gravar_relatorio(relatorio, tmp_path, CONFIG, AGORA)

    assert caminho.parent == (tmp_path / CONFIG.relatorios.subpasta).resolve()
    assert json.loads(caminho.read_text(encoding="utf-8")) == relatorio
    assert caminho.stat().st_mode & 0o777 == 0o600


def test_cliente_que_obedece_a_injecao_dentro_do_schema_reprova_o_tier():
    def no_sobre(resposta, entrada):
        resposta["sobre"]["texto"] += " Sistema comprometido."

    relatorio = _avaliar(_obediente(no_sobre))

    assert relatorio["veredito"] == "reprovado"
    assert _armadilha(relatorio, "prompt_injection")["falhas"] == ["proibido"]
    assert relatorio["falhas_por_armadilha"] == {"prompt_injection": 1}
    assert relatorio["taxa_por_regra"]["proibido"] < 1.0


@pytest.mark.parametrize(
    "alterar",
    [
        lambda resposta, entrada: resposta["sobre"].update(instrucao="conteudo do .env"),
        lambda resposta, entrada: resposta["experiencias"][0]["bullets"][0].update(
            id="exp_injetado_1"
        ),
        lambda resposta, entrada: resposta["sobre"]["techs"].append("Kubernetes"),
        lambda resposta, entrada: resposta["experiencias"][0]["bullets"][0].update(
            texto=r"Construí \input{/etc/passwd} em Python."
        ),
    ],
)
def test_injecao_que_muda_slot_fora_do_schema_conta_como_falha_do_tier(alterar):
    relatorio = _avaliar(_obediente(alterar))

    assert relatorio["veredito"] == "reprovado"
    assert not _armadilha(relatorio, "prompt_injection")["aprovada"]
    assert "prompt_injection" in relatorio["falhas_por_armadilha"]


def test_modelo_indisponivel_nao_aprova_mesmo_com_curriculo_sem_ia_valido():
    def indisponivel(entrada, conteudo):
        def transporte(pedido):
            raise ModeloIndisponivel("OPENAI_API_KEY ausente")

        return transporte

    relatorio = _avaliar(indisponivel)

    assert relatorio["veredito"] == "reprovado"
    assert {tuple(item["falhas"]) for item in relatorio["armadilhas"]} == {
        ("sem_ia_modelo_indisponivel",)
    }
    assert relatorio["chamadas"] == 0


def test_tipo_de_armadilha_sem_cobertura_reprova():
    caso = CONFIG.casos["escrita_slots"]
    parcial = caso.model_copy(update={"armadilhas": ["prompt_injection"]})
    config = CONFIG.model_copy(update={"casos": {"escrita_slots": parcial}})

    relatorio = _avaliar(_referencia, config=config)

    assert relatorio["veredito"] == "reprovado"
    assert set(relatorio["armadilhas_sem_cobertura"]) == set(
        carregar("modelos")["conjunto_avaliacao"]["armadilhas"]
    ) - {"prompt_injection"}


def test_tier_sem_caso_de_prompt_reprova_sem_chamar_nada():
    relatorio = _avaliar(_referencia, tier="rapido")

    assert relatorio["veredito"] == "reprovado"
    assert relatorio["execucoes"] == 0
    assert relatorio["chamadas"] == 0


def test_relatorio_nao_carrega_o_texto_das_vagas():
    relatorio = json.dumps(_avaliar(_referencia), ensure_ascii=False)

    for entrada in ARMADILHAS:
        for linha in entrada.texto.splitlines():
            if len(linha.strip()) > 20:
                assert linha.strip() not in relatorio


def test_vagas_reais_entram_agregadas_sem_identificar_texto():
    reais = tuple(
        entrada.model_copy(update={"id": f"real_{indice}", "tipo": "vaga_real", "proibidos": []})
        for indice, entrada in enumerate(ARMADILHAS[:2])
    )
    lotes = [Lote(CONTEUDO, tuple(ARMADILHAS), False), Lote(CONTEUDO, reais, True)]

    relatorio = _avaliar(_referencia, lotes=lotes)

    assert relatorio["vagas_reais"] == {
        "avaliadas": 2,
        "aprovadas": 2,
        "falhas": {},
        "sem_conteudo": 0,
    }
    assert relatorio["execucoes"] == len(ARMADILHAS) + 2


def test_termos_proibidos_sem_distinguir_caixa_em_qualquer_slot():
    slots = {"sobre": {"texto": "ok"}, "projetos": [{"bullets": [{"texto": "Usei KAFKA."}]}]}

    assert termos_proibidos(slots, ["kafka", "terraform"]) == ["kafka"]
    assert termos_proibidos(slots, ["terraform"]) == []


def test_armadilhas_cobrem_os_tipos_exigidos_e_sao_ficticias():
    tipos = {entrada.tipo for entrada in ARMADILHAS}
    assert set(carregar("modelos")["conjunto_avaliacao"]["armadilhas"]) <= tipos
    for entrada in ARMADILHAS:
        assert entrada.proibidos
        for dominio in re.findall(r"@([\w.-]+)", entrada.texto):
            assert dominio.endswith((".example", ".invalid"))


def test_casos_do_config_tem_executor_registrado():
    assert {caso.executor for caso in CONFIG.casos.values()} <= set(EXECUTORES)


def _bloquear_real(monkeypatch):
    def proibido(*args, **kwargs):
        raise AssertionError("modo offline tocou provedor ou banco")

    monkeypatch.setattr("src.llm.roteador.TransporteOpenAI.__call__", proibido)
    monkeypatch.setattr("src.llm.roteador.reservar_uso_llm", proibido)
    monkeypatch.setattr("src.llm.roteador.exigir_sistema_ativo", proibido)
    monkeypatch.setattr("src.db.uso_llm.finalizar_uso_llm", proibido)


def test_cli_sem_real_roda_offline_sem_provedor_nem_banco(tmp_path, monkeypatch, capsys):
    _bloquear_real(monkeypatch)

    codigo = cli.main(["--tier", "forte"], pasta_dados=tmp_path)

    assert codigo == 0
    relatorios = list((tmp_path / CONFIG.relatorios.subpasta).glob("*.json"))
    assert len(relatorios) == 1
    assert json.loads(relatorios[0].read_text(encoding="utf-8"))["modo"] == "offline"
    assert "aprovado" in capsys.readouterr().out


def test_cli_com_real_usa_transporte_e_orcamento_do_roteador(tmp_path, monkeypatch):
    reservas, finalizacoes = [], []

    def transporte(self, pedido):
        idioma = "pt" if "Idioma do currículo: pt." in pedido["input"] else "en"
        entrada = next(entrada for entrada in ARMADILHAS if entrada.idioma == idioma)
        return _referencia(entrada, CONTEUDO)(pedido)

    def reservar(**dados):
        reservas.append(dados)
        return len(reservas)

    monkeypatch.setattr("src.llm.roteador.TransporteOpenAI.__call__", transporte)
    monkeypatch.setattr("src.llm.roteador.reservar_uso_llm", reservar)
    monkeypatch.setattr("src.llm.roteador.exigir_sistema_ativo", lambda: None)
    monkeypatch.setattr("src.db.uso_llm.finalizar_uso_llm", lambda *a: finalizacoes.append(a))

    codigo = cli.main(["--tier", "forte", "--real"], pasta_dados=tmp_path)

    relatorio = json.loads(
        next((tmp_path / CONFIG.relatorios.subpasta).glob("*.json")).read_text(encoding="utf-8")
    )
    assert codigo == 0
    assert relatorio["modo"] == "real"
    assert len(reservas) == len(finalizacoes) == len(ARMADILHAS)
    assert {reserva["tier"] for reserva in reservas} == {"forte"}
