from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from src.config import carregar
from src.painel import repositorio as modulo_repositorio
from src.painel.app import criar_app
from src.painel.renderizar import HtmlSeguro, renderizar
from src.painel.repositorio import RepositorioFicticio

CONFIG = carregar("painel")
ORIGEM = f"http://127.0.0.1:{CONFIG['porta']}"
TEXTOS = CONFIG["textos"]
FUSO = ZoneInfo(CONFIG["fuso"])
AGORA = datetime(2026, 11, 5, 18, 0, tzinfo=FUSO)
FIXTURE = Path("tests/fixtures/painel_ficticio.yaml")


def relogio():
    return AGORA


def cliente_com(repositorio) -> TestClient:
    return TestClient(criar_app(repositorio=repositorio, relogio=relogio), base_url=ORIGEM)


@pytest.fixture
def cliente() -> TestClient:
    return cliente_com(RepositorioFicticio.de_arquivo(FIXTURE, AGORA))


@pytest.fixture
def cliente_vazio() -> TestClient:
    return cliente_com(RepositorioFicticio.de_dados({}, AGORA))


def test_raiz_leva_para_a_tela_hoje(cliente):
    resposta = cliente.get("/", follow_redirects=False)
    assert resposta.status_code in {302, 303, 307}
    assert resposta.headers["location"] == CONFIG["rota_inicial"]


def test_hoje_lista_os_eventos_do_dia_com_vaga_empresa_e_tipo(cliente):
    resposta = cliente.get("/hoje")
    assert resposta.status_code == 200
    assert "Estagio em Engenharia de Software" in resposta.text
    assert "Empresa Exemplo" in resposta.text
    assert CONFIG["tipos_evento"]["entrevista"]["rotulo"] in resposta.text
    assert "rh@empresa-exemplo.example" in resposta.text
    assert "05/11/2026" in resposta.text


def test_hoje_ordena_do_evento_mais_recente_para_o_mais_antigo(cliente):
    texto = cliente.get("/hoje").text
    assert texto.index("09:12") < texto.index("08:40") < texto.index("07:55")


def test_hoje_marca_email_sem_autenticacao_e_fila(cliente):
    texto = cliente.get("/hoje").text
    assert TEXTOS["comum"]["nao_autenticado"] in texto
    assert CONFIG["tipos_evento"]["suspeito"]["rotulo"] in texto
    assert TEXTOS["comum"]["sem_vaga"] in texto


def test_hoje_lista_as_pendencias_abertas(cliente):
    texto = cliente.get("/hoje").text
    assert "pergunta_nova" in texto
    assert "Formulario pede pretensao salarial" in texto


def test_hoje_nao_lista_evento_de_outro_dia():
    repositorio = RepositorioFicticio.de_dados(
        {
            "eventos": [
                {
                    "id": 1,
                    "hora": "09:00",
                    "dias_atras": 1,
                    "vaga": "Vaga de ontem",
                    "empresa": "Empresa Exemplo",
                    "tipo": "aplicada",
                    "remetente": "rh@empresa-exemplo.example",
                    "autenticado": True,
                    "fila": None,
                }
            ]
        },
        AGORA,
    )
    texto = cliente_com(repositorio).get("/hoje").text
    assert "Vaga de ontem" not in texto
    assert TEXTOS["hoje"]["sem_eventos"] in texto


def test_hoje_vazio_diz_que_nao_ha_nada(cliente_vazio):
    texto = cliente_vazio.get("/hoje").text
    assert TEXTOS["hoje"]["sem_eventos"] in texto
    assert TEXTOS["hoje"]["sem_pendencias"] in texto


def test_candidaturas_agrupa_por_etapa_na_ordem_da_config_com_o_ultimo_evento(cliente):
    texto = cliente.get("/candidaturas").text
    rotulos = {e["estado"]: e["rotulo"] for e in CONFIG["etapas_candidatura"]}
    entrevista = texto.index(f">{rotulos['entrevista']}<")
    confirmada = texto.index(f">{rotulos['aplicada_confirmada']}<")
    encerrada = texto.index(f">{rotulos['encerrada']}<")
    assert entrevista < confirmada < encerrada
    assert texto.index("Estagio em Engenharia de Software") > entrevista
    assert texto.index("Estagio em Engenharia de Software") < confirmada
    assert CONFIG["tipos_evento"]["entrevista"]["rotulo"] in texto
    assert "selecao@casa-de-dados.example" in texto
    assert TEXTOS["candidaturas"]["sem_evento"] in texto


def test_candidaturas_nao_mostra_etapa_sem_vaga(cliente):
    texto = cliente.get("/candidaturas").text
    rotulos = {e["estado"]: e["rotulo"] for e in CONFIG["etapas_candidatura"]}
    assert f">{rotulos['oferta']}<" not in texto
    assert f">{rotulos['rejeitada_pela_empresa']}<" not in texto


def test_candidaturas_vazia_diz_o_que_fazer(cliente_vazio):
    texto = cliente_vazio.get("/candidaturas").text
    assert TEXTOS["candidaturas"]["vazio"] in texto


@pytest.mark.parametrize("rota", ["/hoje", "/candidaturas"])
def test_texto_externo_malicioso_sai_escapado(cliente, rota):
    texto = cliente.get(rota).text
    assert "<script>alert" not in texto
    assert "<img src=x" not in texto
    assert "<b>captcha</b>" not in texto
    assert "&lt;script&gt;alert(&#x27;vaga&#x27;)&lt;/script&gt;" in texto
    assert "&lt;script&gt;alert(&#x27;empresa&#x27;)&lt;/script&gt;" in texto
    assert "&lt;img src=x onerror=alert(1)&gt;" in texto


@pytest.mark.parametrize("rota", ["/hoje", "/candidaturas"])
def test_pagina_nao_tem_script_nem_estilo_inline_nem_origem_externa(cliente, rota):
    resposta = cliente.get(rota)
    texto = resposta.text
    for abertura in re.findall(r"<script\b[^>]*>", texto):
        assert "src=" in abertura
    assert not re.search(r"<style\b", texto)
    assert not re.search(r"\sstyle=", texto)
    assert not re.search(r"<[a-zA-Z][^>]*\son\w+\s*=", texto)
    assert not re.search(r"""(?:src|href)=["']?(?:https?:)?//""", texto)
    assert "/assets/painel.css" in texto
    assert "default-src 'none'" in resposta.headers["content-security-policy"]


@pytest.mark.parametrize("rota", ["/hoje", "/candidaturas"])
def test_pagina_marca_a_tela_atual_na_navegacao(cliente, rota):
    texto = cliente.get(rota).text
    assert texto.count('aria-current="page"') == 1
    assert re.search(rf'href="{rota}"[^>]*aria-current="page"', texto)


@pytest.mark.parametrize("rota", ["/hoje", "/candidaturas"])
def test_pagina_entrega_o_token_csrf_ao_htmx(cliente, rota):
    assert CONFIG["csrf_cabecalho"] in cliente.get(rota).text


class RepositorioQuebrado:
    def eventos_do_dia(self, inicio, fim):
        raise RuntimeError("senha=segredo-que-nao-pode-vazar")

    def pendencias_abertas(self):
        raise RuntimeError("senha=segredo-que-nao-pode-vazar")

    def candidaturas(self, estados):
        raise RuntimeError("senha=segredo-que-nao-pode-vazar")


@pytest.mark.parametrize("rota", ["/hoje", "/candidaturas"])
def test_falha_na_leitura_mostra_erro_sem_detalhe(rota):
    from src.db.conexao import ConfiguracaoBancoInvalida

    class SemBanco(RepositorioQuebrado):
        def eventos_do_dia(self, inicio, fim):
            raise ConfiguracaoBancoInvalida("senha=segredo-que-nao-pode-vazar")

        def pendencias_abertas(self):
            raise ConfiguracaoBancoInvalida("senha=segredo-que-nao-pode-vazar")

        def candidaturas(self, estados):
            raise ConfiguracaoBancoInvalida("senha=segredo-que-nao-pode-vazar")

    resposta = cliente_com(SemBanco()).get(rota)
    assert resposta.status_code == 503
    assert TEXTOS["erro"]["titulo"] in resposta.text
    assert "segredo-que-nao-pode-vazar" not in resposta.text
    assert "content-security-policy" in resposta.headers


def test_erro_inesperado_na_leitura_nao_e_engolido():
    cliente = TestClient(
        criar_app(repositorio=RepositorioQuebrado(), relogio=relogio),
        base_url=ORIGEM,
        raise_server_exceptions=True,
    )
    with pytest.raises(RuntimeError):
        cliente.get("/hoje")


def test_painel_ficticio_avisa_que_os_dados_nao_sao_reais(cliente):
    assert TEXTOS["comum"]["ficticio"] in cliente.get("/hoje").text


def test_painel_com_banco_nao_mostra_o_aviso_de_dados_ficticios(monkeypatch):
    conexoes = FabricaDeConexao()
    monkeypatch.setattr(modulo_repositorio, "conectar", conexoes)
    cliente = TestClient(criar_app(relogio=relogio), base_url=ORIGEM)
    assert TEXTOS["comum"]["ficticio"] not in cliente.get("/hoje").text


class CursorFalso:
    def __init__(self, conexao):
        self.conexao = conexao

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False

    def execute(self, sql, parametros=None):
        self.conexao.consultas.append(sql)
        self.ultima = sql

    def fetchall(self):
        if "pleito.pendencia" in self.ultima:
            return [(7, "captcha", "<b>x</b>", "Vaga A", "Empresa A", AGORA)]
        if "pleito.evento_email" in self.ultima and "LATERAL" not in self.ultima:
            return [(3, "Vaga B", "Empresa B", "oferta", "rh@empresa-b.example", True, None, AGORA)]
        return [
            (5, "Vaga C", "Empresa C", "teste", "teste", "rh@empresa-c.example", AGORA),
            (6, "Vaga D", None, "teste", None, None, None),
        ]


class ConexaoFalsa:
    def __init__(self):
        self.consultas = []
        self.somente_leitura = False
        self.fechada = False

    @property
    def read_only(self):
        return self.somente_leitura

    @read_only.setter
    def read_only(self, valor):
        self.somente_leitura = valor

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        self.fechada = True
        return False

    def cursor(self):
        return CursorFalso(self)


class FabricaDeConexao:
    def __init__(self):
        self.componentes = []
        self.conexoes = []

    def __call__(self, componente):
        self.componentes.append(componente)
        conexao = ConexaoFalsa()
        self.conexoes.append(conexao)
        return conexao


@pytest.fixture
def fabrica(monkeypatch) -> FabricaDeConexao:
    fabrica = FabricaDeConexao()
    monkeypatch.setattr(modulo_repositorio, "conectar", fabrica)
    return fabrica


@pytest.mark.parametrize("rota", ["/hoje", "/candidaturas"])
def test_painel_le_so_com_o_papel_do_painel_e_so_com_select(fabrica, rota):
    cliente = TestClient(criar_app(relogio=relogio), base_url=ORIGEM)
    resposta = cliente.get(rota)
    assert resposta.status_code == 200
    assert fabrica.componentes
    assert set(fabrica.componentes) == {"painel"}
    consultas = [sql for conexao in fabrica.conexoes for sql in conexao.consultas]
    assert consultas
    for sql in consultas:
        assert sql.lstrip().upper().startswith("SELECT")
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER|GRANT)\b", sql.upper())
    for conexao in fabrica.conexoes:
        assert conexao.somente_leitura
        assert conexao.fechada


def test_leitura_do_banco_vira_tela_com_texto_escapado(fabrica):
    cliente = TestClient(criar_app(relogio=relogio), base_url=ORIGEM)
    hoje = cliente.get("/hoje").text
    assert "Vaga B" in hoje
    assert "captcha" in hoje
    assert "&lt;b&gt;x&lt;/b&gt;" in hoje
    candidaturas = cliente.get("/candidaturas").text
    assert "Vaga C" in candidaturas
    assert "Vaga D" in candidaturas
    assert TEXTOS["comum"]["sem_empresa"] in candidaturas


def test_consultas_nomeiam_o_schema_porque_o_login_do_painel_nao_tem_search_path(fabrica):
    cliente = TestClient(criar_app(relogio=relogio), base_url=ORIGEM)
    cliente.get("/hoje")
    cliente.get("/candidaturas")
    for conexao in fabrica.conexoes:
        for sql in conexao.consultas:
            tabelas = re.findall(r"\b(?:FROM|JOIN)\s+([a-z_.]+)", sql)
            assert tabelas
            assert all(tabela.startswith("pleito.") for tabela in tabelas)


def test_renderizar_nao_escapa_fragmento_que_ele_mesmo_gerou():
    fragmento = renderizar("<b>{{x}}</b>", x="<i>")
    assert isinstance(fragmento, HtmlSeguro)
    assert renderizar("{{f}}", f=fragmento) == "<b>&lt;i&gt;</b>"


def test_renderizar_escapa_texto_comum_mesmo_que_pareca_fragmento():
    assert renderizar("{{f}}", f="<b>x</b>") == "&lt;b&gt;x&lt;/b&gt;"
