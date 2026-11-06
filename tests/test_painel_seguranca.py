from __future__ import annotations

import re

import pytest
from fastapi import WebSocket
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.config import carregar
from src.painel import app as modulo_app
from src.painel import seguranca
from src.painel.app import criar_app
from src.painel.renderizar import renderizar

CONFIG = carregar("painel")
PORTA = CONFIG["porta"]
ORIGEM = f"http://127.0.0.1:{PORTA}"
CABECALHO = CONFIG["csrf_cabecalho"]


def montar():
    aplicacao = criar_app()
    acoes = []

    @aplicacao.post("/teste/acao")
    def acao():
        acoes.append(1)
        return PlainTextResponse("feito")

    @aplicacao.put("/teste/troca")
    def troca():
        acoes.append(1)
        return PlainTextResponse("feito")

    @aplicacao.patch("/teste/emenda")
    def emenda():
        acoes.append(1)
        return PlainTextResponse("feito")

    @aplicacao.websocket("/teste/ws")
    async def canal(conexao: WebSocket):
        await conexao.accept()
        acoes.append(1)
        await conexao.close()

    @aplicacao.delete("/teste/apaga")
    def apaga():
        acoes.append(1)
        return PlainTextResponse("feito")

    return aplicacao, acoes


@pytest.fixture
def cliente():
    aplicacao, _ = montar()
    return TestClient(aplicacao, base_url=ORIGEM)


@pytest.fixture
def cliente_com_acoes():
    aplicacao, acoes = montar()
    return TestClient(aplicacao, base_url=ORIGEM), acoes


def token_da_pagina(cliente) -> str:
    pagina = cliente.get("/").text
    return re.search(r'"' + CABECALHO + r'":\s*"([^"]+)"', pagina.replace("&quot;", '"')).group(1)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_host_local_na_porta_da_config_e_aceito(host):
    aplicacao, _ = montar()
    resposta = TestClient(aplicacao, base_url=f"http://{host}:{PORTA}").get("/")
    assert resposta.status_code == 200


@pytest.mark.parametrize(
    "host",
    [
        "evil.com",
        f"evil.com:{PORTA}",
        f"127.0.0.1:{PORTA + 1}",
        "127.0.0.1",
        "localhost",
        f"localhost.evil.com:{PORTA}",
        f"127.0.0.1.evil.com:{PORTA}",
        f"evil.com#127.0.0.1:{PORTA}",
        f"127.0.0.1:{PORTA}@evil.com",
        f"[::1]:{PORTA}",
        "",
    ],
)
def test_host_fora_de_loopback_na_porta_da_config_recebe_400(cliente, host):
    resposta = cliente.get("/", headers={"Host": host})
    assert resposta.status_code == 400


def test_host_repetido_recebe_400(cliente):
    resposta = cliente.get(
        "/", headers=[("Host", f"127.0.0.1:{PORTA}"), ("Host", f"127.0.0.1:{PORTA}")]
    )
    assert resposta.status_code == 400


def test_host_em_maiuscula_e_aceito(cliente):
    assert cliente.get("/", headers={"Host": f"LOCALHOST:{PORTA}"}).status_code == 200


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORTA}", f"evil.com:{PORTA}"])
def test_websocket_e_recusado_com_host_valido_ou_nao(cliente_com_acoes, host):
    cliente, acoes = cliente_com_acoes
    with pytest.raises(WebSocketDisconnect):
        with cliente.websocket_connect("/teste/ws", headers={"Host": host}):
            pass
    assert acoes == []


def test_host_invalido_tambem_e_barrado_em_rota_inexistente_e_estatico(cliente):
    for caminho in ("/nao-existe", "/assets/htmx.min.js"):
        assert cliente.get(caminho, headers={"Host": "evil.com"}).status_code == 400


def test_host_invalido_recebe_400_antes_do_csrf(cliente):
    resposta = cliente.post("/teste/acao", headers={"Host": "evil.com"})
    assert resposta.status_code == 400


def test_hosts_permitidos_vem_da_config(monkeypatch):
    monkeypatch.setitem(CONFIG, "hosts_permitidos", ["127.0.0.1"])
    monkeypatch.setattr(seguranca, "carregar", lambda nome: CONFIG)
    aplicacao, _ = montar()
    bloqueado = TestClient(aplicacao, base_url=f"http://localhost:{PORTA}").get("/")
    liberado = TestClient(aplicacao, base_url=f"http://127.0.0.1:{PORTA}").get("/")
    assert (bloqueado.status_code, liberado.status_code) == (400, 200)


def diretivas(csp: str) -> dict[str, list[str]]:
    partes = [p.strip() for p in csp.split(";") if p.strip()]
    return {p.split()[0]: p.split()[1:] for p in partes}


def respostas_variadas(cliente):
    return [
        cliente.get("/"),
        cliente.get("/assets/htmx.min.js"),
        cliente.get("/nao-existe"),
        cliente.post("/teste/acao"),
        cliente.get("/", headers={"Host": "evil.com"}),
    ]


def test_toda_resposta_tem_csp_estrita_sem_inline_nem_origem_externa(cliente):
    for resposta in respostas_variadas(cliente):
        politica = diretivas(resposta.headers["content-security-policy"])
        assert politica["default-src"] == ["'none'"]
        assert politica["script-src"] == ["'self'"]
        assert politica["style-src"] == ["'self'"]
        assert politica["frame-ancestors"] == ["'none'"]
        assert politica["base-uri"] == ["'none'"]
        for fontes in politica.values():
            for fonte in fontes:
                assert fonte not in ("'unsafe-inline'", "'unsafe-eval'", "*", "data:", "blob:")
                assert not fonte.startswith(("http:", "https:", "//"))


def test_toda_resposta_tem_os_cabecalhos_basicos(cliente):
    for resposta in respostas_variadas(cliente):
        assert resposta.headers["x-content-type-options"] == "nosniff"
        assert resposta.headers["x-frame-options"] == "DENY"
        assert resposta.headers["referrer-policy"] == "no-referrer"
        assert resposta.headers["cache-control"] == "no-store"


def test_csp_vem_da_config(monkeypatch):
    monkeypatch.setitem(CONFIG, "csp", {"default-src": "'none'"})
    monkeypatch.setattr(seguranca, "carregar", lambda nome: CONFIG)
    aplicacao, _ = montar()
    resposta = TestClient(aplicacao, base_url=ORIGEM).get("/")
    assert resposta.headers["content-security-policy"] == "default-src 'none'"


def test_pagina_inicial_nao_tem_script_inline_nem_handler_nem_estilo_inline(cliente):
    pagina = cliente.get("/").text
    for script in re.findall(r"<script\b([^>]*)>(.*?)</script>", pagina, flags=re.S):
        assert "src=" in script[0]
        assert script[1].strip() == ""
    assert not re.search(r"\son[a-z]+\s*=", pagina, flags=re.I)
    assert not re.search(r"\sstyle\s*=", pagina, flags=re.I)
    assert "<style" not in pagina
    assert not re.search(r"(src|href)\s*=\s*[\"']?(https?:)?//", pagina, flags=re.I)
    assert "javascript:" not in pagina.lower()


def test_pagina_desliga_estilo_e_eval_inline_do_htmx(cliente):
    pagina = cliente.get("/").text.replace("&quot;", '"')
    assert '"includeIndicatorStyles": false' in pagina
    assert '"allowEval": false' in pagina


@pytest.mark.parametrize("metodo", ["post", "put", "delete", "patch"])
def test_acao_sem_token_csrf_e_recusada(cliente_com_acoes, metodo):
    cliente, acoes = cliente_com_acoes
    caminho = {
        "post": "/teste/acao",
        "put": "/teste/troca",
        "delete": "/teste/apaga",
        "patch": "/teste/emenda",
    }[metodo]
    resposta = getattr(cliente, metodo)(caminho)
    assert resposta.status_code == 403
    assert acoes == []


@pytest.mark.parametrize("token", ["errado", "", " ", "a" * 64])
def test_acao_com_token_errado_e_recusada(cliente_com_acoes, token):
    cliente, acoes = cliente_com_acoes
    resposta = cliente.post("/teste/acao", headers={CABECALHO: token})
    assert resposta.status_code == 403
    assert acoes == []


def test_token_em_parametro_ou_cookie_nao_vale(cliente_com_acoes):
    cliente, acoes = cliente_com_acoes
    token = token_da_pagina(cliente)
    cliente.cookies.set("csrf", token)
    resposta = cliente.post("/teste/acao", params={"csrf": token}, data={"csrf": token})
    assert resposta.status_code == 403
    assert acoes == []


def test_acao_com_token_da_pagina_passa(cliente_com_acoes):
    cliente, acoes = cliente_com_acoes
    resposta = cliente.post("/teste/acao", headers={CABECALHO: token_da_pagina(cliente)})
    assert resposta.status_code == 200
    assert acoes == [1]


def test_tamanho_do_token_vem_da_config(monkeypatch):
    monkeypatch.setitem(CONFIG, "token_bytes", 48)
    monkeypatch.setattr(modulo_app, "carregar", lambda nome: CONFIG)
    aplicacao, _ = montar()
    token = token_da_pagina(TestClient(aplicacao, base_url=ORIGEM))
    assert len(token) == len(seguranca.gerar_token(48))


def test_esquema_da_origem_vem_da_config(monkeypatch, cliente_com_acoes):
    monkeypatch.setitem(CONFIG, "esquema_origem", "https")
    monkeypatch.setattr(seguranca, "carregar", lambda nome: CONFIG)
    aplicacao, acoes = montar()
    cliente = TestClient(aplicacao, base_url=ORIGEM)
    token = token_da_pagina(cliente)
    http = cliente.post("/teste/acao", headers={CABECALHO: token, "Origin": ORIGEM})
    https = cliente.post(
        "/teste/acao", headers={CABECALHO: token, "Origin": ORIGEM.replace("http", "https")}
    )
    assert (http.status_code, https.status_code) == (403, 200)


def test_fetch_site_aceitos_vem_da_config(monkeypatch):
    monkeypatch.setitem(CONFIG, "fetch_site_aceitos", ["same-origin"])
    monkeypatch.setattr(seguranca, "carregar", lambda nome: CONFIG)
    aplicacao, _ = montar()
    cliente = TestClient(aplicacao, base_url=ORIGEM)
    token = token_da_pagina(cliente)
    resposta = cliente.post("/teste/acao", headers={CABECALHO: token, "Sec-Fetch-Site": "none"})
    assert resposta.status_code == 403


def test_token_e_estavel_no_processo_e_difere_entre_processos():
    aplicacao_a, _ = montar()
    aplicacao_b, _ = montar()
    cliente_a = TestClient(aplicacao_a, base_url=ORIGEM)
    cliente_b = TestClient(aplicacao_b, base_url=ORIGEM)
    token_a = token_da_pagina(cliente_a)
    assert token_a == token_da_pagina(cliente_a)
    assert len(token_a) >= 32
    assert token_a != token_da_pagina(cliente_b)
    assert cliente_b.post("/teste/acao", headers={CABECALHO: token_a}).status_code == 403


def test_leitura_nao_exige_token(cliente):
    assert cliente.get("/").status_code == 200
    assert cliente.head("/").status_code != 403


@pytest.mark.parametrize(
    "origem",
    ["http://evil.com", "https://127.0.0.1:" + str(PORTA), f"http://127.0.0.1:{PORTA + 1}", "null"],
)
def test_origin_cruzado_e_recusado_mesmo_com_token_valido(cliente_com_acoes, origem):
    cliente, acoes = cliente_com_acoes
    token = token_da_pagina(cliente)
    resposta = cliente.post("/teste/acao", headers={CABECALHO: token, "Origin": origem})
    assert resposta.status_code == 403
    assert acoes == []


@pytest.mark.parametrize("origem", [ORIGEM, f"http://localhost:{PORTA}"])
def test_origin_do_proprio_painel_passa(cliente_com_acoes, origem):
    cliente, acoes = cliente_com_acoes
    token = token_da_pagina(cliente)
    resposta = cliente.post("/teste/acao", headers={CABECALHO: token, "Origin": origem})
    assert resposta.status_code == 200
    assert acoes == [1]


def test_fetch_cross_site_e_recusado_mesmo_com_token_valido(cliente_com_acoes):
    cliente, acoes = cliente_com_acoes
    token = token_da_pagina(cliente)
    resposta = cliente.post(
        "/teste/acao", headers={CABECALHO: token, "Sec-Fetch-Site": "cross-site"}
    )
    assert resposta.status_code == 403
    assert acoes == []


def test_pagina_entrega_o_token_ao_htmx_por_hx_headers_sem_script_inline(cliente):
    pagina = cliente.get("/").text
    assert "hx-headers=" in pagina
    assert token_da_pagina(cliente) in pagina
    assert '<script src="/assets/htmx.min.js"' in pagina


def test_texto_externo_e_escapado_ao_renderizar():
    modelo = "<h1>{{titulo}}</h1><a title=\"{{titulo}}\">x</a>"
    ataque = '<script>alert(1)</script>" onerror="alert(2)\' <img src=x onerror=alert(3)>'
    saida = renderizar(modelo, titulo=ataque)
    assert "<script>" not in saida
    assert "<img" not in saida
    assert saida.count('"') == 2
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in saida
    assert "&quot; onerror=&quot;" in saida


def test_renderizar_nao_reinterpreta_placeholder_dentro_do_valor():
    saida = renderizar("{{a}}|{{b}}", a="{{b}}", b="<i>")
    assert saida == "{{b}}|&lt;i&gt;"


def test_renderizar_recusa_placeholder_sem_valor():
    with pytest.raises(KeyError):
        renderizar("{{a}}{{b}}", a="x")


def test_titulo_de_vaga_com_script_chega_escapado_na_resposta_http():
    aplicacao, _ = montar()

    @aplicacao.get("/teste/vaga")
    def vaga():
        return HTMLResponse(
            renderizar("<h2>{{titulo}}</h2>", titulo="<script>alert(1)</script>Dev")
        )

    corpo = TestClient(aplicacao, base_url=ORIGEM).get("/teste/vaga").text
    assert "<script>" not in corpo
    assert corpo == "<h2>&lt;script&gt;alert(1)&lt;/script&gt;Dev</h2>"

