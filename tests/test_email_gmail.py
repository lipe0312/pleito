from __future__ import annotations

import copy
import inspect
import json

import httpx
import pytest
import respx

from src.config import carregar
from src.email.configuracao import RotuloRecusado, configuracao_gmail
from src.email.gmail import ClienteGmail, IdentificadorInvalido
from src.email.keychain import TokenAusente
from src.email.oauth import ClienteOAuth

CLIENTE = ClienteOAuth("id-ficticio.apps.exemplo", "segredo-ficticio")
PROIBIDOS = ("delete", "trash", "lixeira", "excluir", "forward", "encaminhar", "send",
             "enviar", "reply", "responder", "draft", "rascunho", "import", "insert")


@pytest.fixture
def cfg():
    return configuracao_gmail(copy.deepcopy(carregar("emails")))


class ChaveFalsa:
    def __init__(self, valor: str | None = "refresh-ficticio") -> None:
        self.valor = valor
        self.gravados: list[str] = []

    def ler(self) -> str:
        if self.valor is None:
            raise TokenAusente
        return self.valor

    def gravar(self, valor: str) -> None:
        self.gravados.append(valor)
        self.valor = valor


def _cliente(cfg, chave=None) -> ClienteGmail:
    return ClienteGmail(cfg, chave or ChaveFalsa(), httpx.Client(), CLIENTE)


def _token(cfg, *respostas):
    return respx.post(cfg.url_token).mock(side_effect=list(respostas))


def _acesso(valor: str = "acesso-1", rotacionado: str | None = None) -> httpx.Response:
    corpo = {"access_token": valor}
    if rotacionado:
        corpo["refresh_token"] = rotacionado
    return httpx.Response(200, json=corpo)


def test_cliente_expoe_so_listar_ler_rotular_e_arquivar():
    publicos = {
        nome for nome, _ in inspect.getmembers(ClienteGmail) if not nome.startswith("_")
    }
    assert publicos == {"listar", "ler", "rotular", "arquivar"}


def test_nenhum_atributo_do_cliente_tem_nome_destrutivo_ou_de_envio():
    nomes = [nome.lower() for nome in dir(ClienteGmail)]
    assert not [nome for nome in nomes for palavra in PROIBIDOS if palavra in nome]


@respx.mock
def test_listar_usa_consulta_e_limite(cfg):
    _token(cfg, _acesso())
    rota = respx.get(f"{cfg.url_api}/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "a1"}]})
    )
    assert _cliente(cfg).listar("label:Candidaturas", 5) == [{"id": "a1"}]
    pedido = rota.calls.last.request
    assert pedido.url.params["q"] == "label:Candidaturas"
    assert pedido.url.params["maxResults"] == "5"
    assert pedido.headers["Authorization"] == "Bearer acesso-1"


@respx.mock
def test_listar_sem_mensagens_devolve_lista_vazia(cfg):
    _token(cfg, _acesso())
    respx.get(f"{cfg.url_api}/messages").mock(return_value=httpx.Response(200, json={}))
    assert _cliente(cfg).listar("", 1) == []


@respx.mock
def test_ler_busca_a_mensagem(cfg):
    _token(cfg, _acesso())
    respx.get(f"{cfg.url_api}/messages/18abc").mock(
        return_value=httpx.Response(200, json={"id": "18abc"})
    )
    assert _cliente(cfg).ler("18abc") == {"id": "18abc"}


@respx.mock
def test_rotular_chama_modify_com_os_ids(cfg):
    _token(cfg, _acesso())
    rota = respx.post(f"{cfg.url_api}/messages/18abc/modify").mock(
        return_value=httpx.Response(200, json={"id": "18abc"})
    )
    _cliente(cfg).rotular("18abc", ["Label_1"], ["Label_2"])
    assert json.loads(rota.calls.last.request.content) == {
        "addLabelIds": ["Label_1"],
        "removeLabelIds": ["Label_2"],
    }


@respx.mock
def test_arquivar_so_remove_a_caixa_de_entrada(cfg):
    _token(cfg, _acesso())
    rota = respx.post(f"{cfg.url_api}/messages/18abc/modify").mock(
        return_value=httpx.Response(200, json={"id": "18abc"})
    )
    _cliente(cfg).arquivar("18abc")
    assert json.loads(rota.calls.last.request.content) == {
        "addLabelIds": [],
        "removeLabelIds": [cfg.rotulo_caixa_entrada],
    }


@pytest.mark.parametrize("identificador", ["18abc/trash", "../drafts/send", "18abc?x=1", ""])
@respx.mock
def test_identificador_que_muda_o_caminho_e_recusado_sem_chamar_a_api(cfg, identificador):
    token = _token(cfg, _acesso())
    with pytest.raises(IdentificadorInvalido):
        _cliente(cfg).rotular(identificador, ["Label_1"], [])
    assert token.call_count == 0


@respx.mock
def test_401_renova_o_token_uma_vez(cfg):
    token = _token(cfg, _acesso("acesso-1"), _acesso("acesso-2"))
    rota = respx.get(f"{cfg.url_api}/messages/18abc").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"id": "18abc"})]
    )
    assert _cliente(cfg).ler("18abc") == {"id": "18abc"}
    assert token.call_count == 2
    assert rota.calls.last.request.headers["Authorization"] == "Bearer acesso-2"


@respx.mock
def test_401_repetido_nao_entra_em_laco(cfg):
    token = _token(cfg, _acesso("acesso-1"), _acesso("acesso-2"))
    respx.get(f"{cfg.url_api}/messages/18abc").mock(return_value=httpx.Response(401))
    with pytest.raises(httpx.HTTPStatusError):
        _cliente(cfg).ler("18abc")
    assert token.call_count == 2


@respx.mock
def test_refresh_token_rotacionado_pelo_google_e_regravado(cfg):
    _token(cfg, _acesso(rotacionado="refresh-novo"))
    respx.get(f"{cfg.url_api}/messages/18abc").mock(
        return_value=httpx.Response(200, json={"id": "18abc"})
    )
    chave = ChaveFalsa()
    _cliente(cfg, chave).ler("18abc")
    assert chave.gravados == ["refresh-novo"]


@respx.mock
def test_sem_token_no_keychain_nao_chama_a_rede(cfg):
    token = _token(cfg, _acesso())
    with pytest.raises(TokenAusente):
        _cliente(cfg, ChaveFalsa(None)).ler("18abc")
    assert token.call_count == 0


@respx.mock
def test_listar_respeita_o_teto_do_config(cfg):
    _token(cfg, _acesso())
    rota = respx.get(f"{cfg.url_api}/messages").mock(return_value=httpx.Response(200, json={}))
    _cliente(cfg).listar("", cfg.listar_maximo * 100)
    assert rota.calls.last.request.url.params["maxResults"] == str(cfg.listar_maximo)


@pytest.mark.parametrize(
    "rotulo",
    ["TRASH", "SPAM", "SENT", "DRAFT", "INBOX", "label_1", "Label_", "Label_1/../TRASH", ""],
)
@pytest.mark.parametrize("lado", ["adicionar", "remover"])
@respx.mock
def test_rotulo_de_sistema_fora_da_allowlist_e_recusado_sem_chamar_a_api(cfg, rotulo, lado):
    token = _token(cfg, _acesso())
    modify = respx.post(f"{cfg.url_api}/messages/18abc/modify").mock(
        return_value=httpx.Response(200, json={"id": "18abc"})
    )
    argumentos = {"adicionar": [], "remover": []}
    argumentos[lado] = ["Label_1", rotulo]
    with pytest.raises(RotuloRecusado):
        _cliente(cfg).rotular("18abc", **argumentos)
    assert token.call_count == 0
    assert modify.call_count == 0


@respx.mock
def test_rotulo_de_sistema_da_allowlist_do_config_e_aceito(cfg):
    _token(cfg, _acesso())
    rota = respx.post(f"{cfg.url_api}/messages/18abc/modify").mock(
        return_value=httpx.Response(200, json={"id": "18abc"})
    )
    permitido = sorted(cfg.rotulos_sistema_permitidos)[0]
    _cliente(cfg).rotular("18abc", ["Label_7"], [permitido])
    assert json.loads(rota.calls.last.request.content) == {
        "addLabelIds": ["Label_7"],
        "removeLabelIds": [permitido],
    }
