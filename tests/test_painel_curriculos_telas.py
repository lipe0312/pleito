from __future__ import annotations

import re

import pytest
from apoio_painel_curriculos import PDF_BYTES, gravar_json, gravar_versao, pasta_da_vaga, violacao
from apoio_painel_telas import AGORA, ATAQUE, CONFIG, ORIGEM, montar
from fastapi.testclient import TestClient

from src.painel.curriculos import Curriculo, LinhaDeDiff, RepositorioArquivosCurriculos
from src.painel.ficticio import ConteudoFicticio, CurriculosFicticio

TEXTOS = CONFIG["textos"]
ROTAS = ["/curriculos", "/curriculos/vaga/101", "/projetos"]


@pytest.fixture
def cliente():
    return montar()


def test_lista_separa_familias_e_versoes_por_vaga_com_contagem(cliente):
    texto = cliente.get("/curriculos").text
    assert TEXTOS["curriculos"]["familias"] in texto
    assert TEXTOS["curriculos"]["vagas"] in texto
    assert "backend_arquitetura (pt)" in texto
    assert "Vaga 101" in texto
    assert 'href="/curriculos/vaga/101"' in texto


def test_selo_funcional_so_nas_versoes_sem_bloqueio_com_pdf(cliente):
    texto = cliente.get("/curriculos").text
    linhas = {
        nome: linha
        for nome, linha in zip(
            ["backend_pt", "dados_en", "101", "102"], texto.split("<li class=")[1:], strict=True
        )
    }
    funcional = TEXTOS["curriculos"]["funcional"]
    assert funcional in linhas["backend_pt"]
    assert funcional in linhas["101"]
    assert funcional not in linhas["dados_en"]
    assert TEXTOS["curriculos"]["com_bloqueio"] in linhas["dados_en"]
    assert funcional not in linhas["102"]
    assert TEXTOS["curriculos"]["com_bloqueio"] in linhas["102"]


def test_lista_mostra_tentativas_e_custo_do_laco(cliente):
    texto = cliente.get("/curriculos").text
    assert "3 tentativas" in texto
    assert "1 tentativa" in texto
    assert "US$ 0,0420" in texto
    assert "US$ 0,0140" in texto


def test_detalhe_embute_o_pdf_no_mesmo_painel(cliente):
    texto = cliente.get("/curriculos/vaga/101").text
    assert re.search(r'<iframe class="pdf" src="/pdf/vaga/101"', texto)
    assert 'target="_blank" rel="noopener noreferrer"' in texto


def test_detalhe_mostra_violacoes_com_codigo_nivel_e_sugestao(cliente):
    texto = cliente.get("/curriculos/vaga/101").text
    assert "V20 pontuacao" in texto
    assert "Bullet sem ponto final." in texto
    assert TEXTOS["curriculo"]["nivel_indicio"] in texto
    assert "Termine o bullet com ponto." in texto


def test_detalhe_mostra_diff_contra_a_familia_com_sinais(cliente):
    texto = cliente.get("/curriculos/vaga/101").text
    assert TEXTOS["curriculo"]["base_familia"].format(base="backend_arquitetura (pt)") in texto
    assert "diff__lado--saiu" in texto and "diff__lado--entrou" in texto
    assert '<span class="sinal">−</span>' in texto
    assert '<span class="sinal">+</span>' in texto
    assert "Montou o painel local com HTMX." in texto


def test_detalhe_de_familia_mostra_diff_contra_a_versao_anterior_e_o_historico(cliente):
    texto = cliente.get("/curriculos/familia/backend_pt").text
    assert TEXTOS["curriculo"]["base_anterior"] in texto
    assert "mais foco em APIs" in texto
    assert "v1, tentativa 1" in texto and "v2, tentativa 3" in texto


def test_detalhe_sem_pdf_nao_cria_frame_e_diz_porque(cliente):
    texto = cliente.get("/curriculos/familia/dados_en").text
    assert "<iframe" not in texto
    assert TEXTOS["curriculo"]["sem_pdf"] in texto
    assert "Tecnologia fora do inventario: Fortran." in texto
    assert TEXTOS["curriculo"]["base_nenhuma"] in texto


@pytest.mark.parametrize("rota", ["/curriculos/vaga/999", "/curriculos/outro/101"])
def test_curriculo_inexistente_responde_404_com_texto_da_config(cliente, rota):
    resposta = cliente.get(rota)
    assert resposta.status_code == 404
    assert TEXTOS["curriculo_nao_encontrado"]["titulo"] in resposta.text


def test_pdf_ficticio_e_gerado_em_memoria_com_cabecalhos_do_frame_same_origin(cliente):
    resposta = cliente.get("/pdf/vaga/101")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF-")
    assert resposta.headers["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in resposta.headers["content-security-policy"]
    assert resposta.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("rota", ["/pdf/familia/dados_en", "/pdf/vaga/999", "/pdf/outro/101"])
def test_pdf_ausente_ou_inexistente_responde_404(cliente, rota):
    assert cliente.get(rota).status_code == 404


@pytest.mark.parametrize("rota", [*ROTAS, "/pdf/vaga/101"])
def test_rotas_novas_recusam_host_de_fora(cliente, rota):
    resposta = cliente.get(rota, headers={"host": "evil.example"})
    assert resposta.status_code == 400


def test_pagina_nao_carrega_nada_de_fora_da_maquina(cliente):
    for rota in ROTAS:
        texto = cliente.get(rota).text
        assert not re.search(r'(?:src|href|action)="(?:https?:)?//', texto)
        assert "cdn" not in texto.lower()


def test_titulo_de_vaga_com_tag_script_aparece_como_texto(cliente):
    lista = cliente.get("/curriculos").text
    detalhe = cliente.get("/curriculos/vaga/102").text
    for texto in (lista, detalhe):
        assert ATAQUE not in texto
        assert "&lt;script&gt;alert(&#x27;vaga&#x27;)&lt;/script&gt;" in texto


def test_violacao_com_html_aparece_escapada(cliente):
    texto = cliente.get("/curriculos/vaga/102").text
    assert "<img src=x" not in texto
    assert "&lt;img src=x onerror=alert(1)&gt;" in texto
    assert "<b>reescreva</b>" not in texto
    assert "&lt;b&gt;reescreva&lt;/b&gt;" in texto


def test_diff_com_script_aparece_escapado():
    base = CurriculosFicticio.de_dados({}, AGORA)
    curriculo = Curriculo(
        tipo="vaga", id="1", titulo="x", versoes=(), violacoes=None, tentativas=0,
        custo_usd=0, tem_pdf=False, projetos=(), base_tipo="anterior", base_rotulo="",
        diff=(LinhaDeDiff("sobre", ("<script>a()</script>",), ("<script>b()</script>",)),),
    )
    base._curriculos.append(curriculo)
    texto = montar(curriculos=base).get("/curriculos/vaga/1").text
    assert "<script>a()" not in texto and "<script>b()" not in texto
    assert "&lt;script&gt;a()&lt;/script&gt;" in texto


def cliente_de_arquivos(tmp_path) -> TestClient:
    return montar(
        curriculos=RepositorioArquivosCurriculos(tmp_path),
        conteudo=ConteudoFicticio.de_dados({}),
    )


def test_arquivos_reais_aparecem_com_selo_pdf_e_sem_vazar_caminho(tmp_path):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), violacoes=[violacao("ok")])
    cliente = cliente_de_arquivos(tmp_path)
    lista = cliente.get("/curriculos").text
    assert TEXTOS["curriculos"]["funcional"] in lista
    assert str(tmp_path) not in lista
    pdf = cliente.get("/pdf/vaga/7")
    assert pdf.content == PDF_BYTES
    assert cliente.get("/curriculos/vaga/7").status_code == 200


def test_arquivos_reais_com_bloqueio_nao_ganham_selo(tmp_path):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), violacoes=[violacao("bloqueia")])
    texto = cliente_de_arquivos(tmp_path).get("/curriculos").text
    assert TEXTOS["curriculos"]["funcional"] not in texto
    assert TEXTOS["curriculos"]["com_bloqueio"] in texto


@pytest.mark.parametrize("ident", ["..", "%2e%2e", "..%2fsegredo", "7%00", "a b"])
def test_pdf_nao_sai_da_pasta_de_curriculos(tmp_path, ident):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    (tmp_path / "segredo.pdf").write_bytes(b"%PDF-1.4 segredo")
    resposta = cliente_de_arquivos(tmp_path).get(f"/pdf/vaga/{ident}")
    assert resposta.status_code in {404, 422}
    assert b"segredo" not in resposta.content


def test_arquivo_corrompido_vira_pagina_de_erro_sem_vazar_a_excecao(tmp_path):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    gravar_json(pasta_da_vaga(tmp_path, "7") / "historico.json", ["nao", "e", "objeto"])
    resposta = cliente_de_arquivos(tmp_path).get("/curriculos")
    assert resposta.status_code == 503
    assert TEXTOS["erro_dados"]["titulo"] in resposta.text
    assert "historico" not in resposta.text
    assert ORIGEM not in resposta.text
