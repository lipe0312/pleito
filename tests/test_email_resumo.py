from __future__ import annotations

import base64
import copy
import json
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

import httpx
import pytest
import respx

from src.config import carregar
from src.email.configuracao import configuracao_gmail
from src.email.oauth import ClienteOAuth
from src.email.resumo import (
    CabecalhoRecusado,
    ClienteResumo,
    DestinoRecusado,
    RotuloNaoAplicado,
    configuracao_resumo,
    corpo_do_dia,
    executar,
    montar,
)
from src.email.rotulos import RotuloAusente

DESTINO = "destino@exemplo.invalid"
OUTRO = "outro@exemplo.invalid"
ID_PRONTAS = "Label_77"
CLIENTE = ClienteOAuth("id-ficticio.apps.exemplo", "segredo-ficticio")


class ChaveFalsa:
    def ler(self) -> str:
        return "refresh-ficticio"

    def gravar(self, valor: str) -> None:
        pass


@pytest.fixture
def cfg():
    return configuracao_gmail(copy.deepcopy(carregar("emails")))


@pytest.fixture
def resumo():
    return configuracao_resumo()


def _ambiente(resumo, destino: str = DESTINO) -> dict[str, str]:
    return {resumo.variavel_destino: destino}


def _cliente(cfg, resumo, destino: str = DESTINO) -> ClienteResumo:
    return ClienteResumo(
        cfg, ChaveFalsa(), httpx.Client(), _ambiente(resumo, destino), resumo, CLIENTE
    )


def _rotas(cfg, resumo, rotulos=None):
    respx.post(cfg.url_token).mock(
        return_value=httpx.Response(200, json={"access_token": "acesso-1"})
    )
    nomes = rotulos if rotulos is not None else [{"id": ID_PRONTAS, "name": resumo.rotulo}]
    respx.get(f"{cfg.url_api}/labels").mock(
        return_value=httpx.Response(200, json={"labels": nomes})
    )
    envio = respx.post(f"{cfg.url_api}/messages/send").mock(
        return_value=httpx.Response(200, json={"id": "enviada1"})
    )
    modify = respx.post(f"{cfg.url_api}/messages/enviada1/modify").mock(
        return_value=httpx.Response(200, json={"id": "enviada1"})
    )
    return envio, modify


def _mensagem_enviada(rota) -> EmailMessage:
    raw = json.loads(rota.calls.last.request.content)["raw"]
    return BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw))


def test_rotulo_do_resumo_e_candidaturas_prontas(resumo):
    assert resumo.rotulo == "Candidaturas/Prontas"


def test_dia_sem_vaga_boa_diz_isso(resumo):
    assert corpo_do_dia(0, resumo) == carregar("resumo")["corpo"]["nenhuma"]
    assert "nenhuma vaga pronta hoje" in corpo_do_dia(0, resumo).lower()


def test_corpo_traz_a_contagem(resumo):
    assert corpo_do_dia(1, resumo) == carregar("resumo")["corpo"]["uma"]
    assert "3" in corpo_do_dia(3, resumo)


def test_contagem_negativa_e_recusada(resumo):
    with pytest.raises(ValueError):
        corpo_do_dia(-1, resumo)


def test_mensagem_vai_so_para_o_destino_do_ambiente(resumo):
    mensagem = montar(_ambiente(resumo), resumo, 2)
    assert mensagem.get_all("To") == [DESTINO]
    assert mensagem["Subject"] == resumo.assunto
    for cabecalho in ("Cc", "Bcc"):
        assert mensagem.get(cabecalho) is None


@pytest.mark.parametrize(
    "destino",
    [
        "",
        "   ",
        f"{DESTINO}, {OUTRO}",
        f"{DESTINO};{OUTRO}",
        f"Filipe <{DESTINO}>",
        f"{DESTINO}\r\nBcc: {OUTRO}",
        f"{DESTINO}\nCc: {OUTRO}",
        "sem-arroba.invalid",
        "destino@exémplo.invalid",
        "dèstino@exemplo.invalid",
        "destino@exemplo.invalid\u200b",
        "destino@exemplo\uff0einvalid",
        "a@b",
    ],
)
def test_destino_invalido_no_ambiente_e_recusado(resumo, destino):
    with pytest.raises(DestinoRecusado):
        montar(_ambiente(resumo, destino), resumo, 0)


def test_destino_ausente_no_ambiente_e_recusado(resumo):
    with pytest.raises(DestinoRecusado):
        montar({}, resumo, 0)


def test_erro_de_destino_nao_repete_o_valor(resumo):
    with pytest.raises(DestinoRecusado) as erro:
        montar(_ambiente(resumo, f"{DESTINO}, {OUTRO}"), resumo, 0)
    assert OUTRO not in str(erro.value)


@pytest.mark.parametrize("assunto", ["resumo\r\nBcc: outro@exemplo.invalid", "a\nb", ""])
def test_assunto_com_quebra_de_linha_ou_vazio_e_recusado(assunto):
    dados = copy.deepcopy(carregar("resumo"))
    dados["assunto"] = assunto
    with pytest.raises(CabecalhoRecusado):
        configuracao_resumo(dados)


@respx.mock
def test_envio_vai_ao_destino_e_recebe_o_rotulo_prontas(cfg, resumo):
    envio, modify = _rotas(cfg, resumo)
    assert _cliente(cfg, resumo).enviar_resumo(montar(_ambiente(resumo), resumo, 0)) == (
        "enviada1"
    )
    enviada = _mensagem_enviada(envio)
    assert enviada.get_all("To") == [DESTINO]
    assert enviada.get("Cc") is None and enviada.get("Bcc") is None
    assert "nenhuma vaga pronta hoje" in enviada.get_content().lower()
    assert json.loads(modify.calls.last.request.content) == {
        "addLabelIds": [ID_PRONTAS],
        "removeLabelIds": [],
    }


def _forjada(resumo, **cabecalhos) -> EmailMessage:
    mensagem = EmailMessage(policy=policy.SMTP)
    mensagem["Subject"] = resumo.assunto
    for nome, valor in cabecalhos.items():
        mensagem[nome.replace("_", "-")] = valor
    mensagem.set_content("x")
    return mensagem


@pytest.mark.parametrize(
    "cabecalhos",
    [
        {"To": OUTRO},
        {"To": f"{DESTINO}, {OUTRO}"},
        {"To": DESTINO, "Cc": OUTRO},
        {"To": DESTINO, "Bcc": OUTRO},
        {"To": DESTINO, "Resent_To": OUTRO},
        {"To": DESTINO, "Resent_Bcc": OUTRO},
        {},
    ],
)
@respx.mock
def test_mensagem_forjada_para_outro_destinatario_nao_sai(cfg, resumo, cabecalhos):
    envio, modify = _rotas(cfg, resumo)
    with pytest.raises(DestinoRecusado):
        _cliente(cfg, resumo).enviar_resumo(_forjada(resumo, **cabecalhos))
    assert envio.call_count == 0
    assert modify.call_count == 0


@respx.mock
def test_dois_cabecalhos_to_com_o_destino_nao_saem(cfg, resumo):
    envio, _ = _rotas(cfg, resumo)
    bruto = f"To: {DESTINO}\r\nTo: {DESTINO}\r\nSubject: x\r\n\r\nx\r\n".encode()
    mensagem = BytesParser(policy=policy.default).parsebytes(bruto)
    with pytest.raises(DestinoRecusado):
        _cliente(cfg, resumo).enviar_resumo(mensagem)
    assert envio.call_count == 0


@respx.mock
def test_cliente_rele_o_destino_do_ambiente_e_nao_do_chamador(cfg, resumo):
    envio, _ = _rotas(cfg, resumo)
    mensagem = montar(_ambiente(resumo, OUTRO), resumo, 0)
    with pytest.raises(DestinoRecusado):
        _cliente(cfg, resumo, DESTINO).enviar_resumo(mensagem)
    assert envio.call_count == 0


@respx.mock
def test_cliente_com_destino_vazio_nao_envia(cfg, resumo):
    envio, _ = _rotas(cfg, resumo)
    with pytest.raises(DestinoRecusado):
        _cliente(cfg, resumo, "").enviar_resumo(_forjada(resumo, To=DESTINO))
    assert envio.call_count == 0


@respx.mock
def test_sem_rotulo_prontas_na_conta_nada_sai(cfg, resumo):
    envio, _ = _rotas(cfg, resumo, rotulos=[{"id": "Label_1", "name": "Outro"}])
    with pytest.raises(RotuloAusente):
        _cliente(cfg, resumo).enviar_resumo(montar(_ambiente(resumo), resumo, 0))
    assert envio.call_count == 0


def _sem_cliente(_variaveis, _http):
    raise AssertionError("dry-run nao pode criar cliente")


def test_comando_padrao_e_dry_run_sem_cliente(resumo, capsys):
    assert executar([], _ambiente(resumo), _sem_cliente) == 0
    saida = capsys.readouterr().out
    assert resumo.assunto in saida
    assert "nenhuma vaga pronta hoje" in saida.lower()
    assert DESTINO not in saida


def test_comando_com_destino_invalido_falha_antes_de_tudo(resumo, capsys):
    assert executar(["--enviar"], _ambiente(resumo, f"{DESTINO},{OUTRO}"), _sem_cliente) == 2
    assert OUTRO not in capsys.readouterr().err


@respx.mock
def test_comando_com_enviar_usa_o_cliente_do_resumo(cfg, resumo):
    envio, modify = _rotas(cfg, resumo)
    criados = []

    def criar(variaveis, http):
        cliente = ClienteResumo(cfg, ChaveFalsa(), http, variaveis, resumo, CLIENTE)
        criados.append(cliente)
        return cliente

    assert executar(["--enviar", "--prontas", "2"], _ambiente(resumo), criar) == 0
    assert len(criados) == 1
    assert "2" in _mensagem_enviada(envio).get_content()
    assert modify.call_count == 1


def test_chave_de_rotulo_ausente_em_rotulos_yaml_tem_mensagem_clara():
    dados = copy.deepcopy(carregar("resumo"))
    dados["rotulo"] = "inexistente"
    with pytest.raises(RotuloAusente, match="config/rotulos.yaml"):
        configuracao_resumo(dados)


def _modify_falha(cfg, resumo):
    envio, modify = _rotas(cfg, resumo)
    modify.mock(return_value=httpx.Response(500))
    return envio, modify


@respx.mock
def test_rotulo_que_falha_depois_do_envio_informa_o_id_e_nao_reenvia(cfg, resumo):
    envio, _ = _modify_falha(cfg, resumo)
    with pytest.raises(RotuloNaoAplicado) as erro:
        _cliente(cfg, resumo).enviar_resumo(montar(_ambiente(resumo), resumo, 0))
    assert erro.value.identificador == "enviada1"
    assert "enviada1" in str(erro.value)
    assert envio.call_count == 1


@respx.mock
def test_comando_com_rotulo_que_falha_sai_com_erro_e_avisa_para_nao_reenviar(
    cfg, resumo, capsys
):
    envio, _ = _modify_falha(cfg, resumo)

    def criar(variaveis, http):
        return ClienteResumo(cfg, ChaveFalsa(), http, variaveis, resumo, CLIENTE)

    assert executar(["--enviar"], _ambiente(resumo), criar) not in (0, 2)
    erro = capsys.readouterr().err
    assert "enviada1" in erro
    assert "não rode de novo" in erro
    assert envio.call_count == 1


@respx.mock
def test_comando_sem_rotulo_na_conta_recusa_sem_enviar(cfg, resumo, capsys):
    envio, _ = _rotas(cfg, resumo, rotulos=[])

    def criar(variaveis, http):
        return ClienteResumo(cfg, ChaveFalsa(), http, variaveis, resumo, CLIENTE)

    assert executar(["--enviar"], _ambiente(resumo), criar) == 2
    assert "crie-o no Gmail" in capsys.readouterr().err
    assert envio.call_count == 0
