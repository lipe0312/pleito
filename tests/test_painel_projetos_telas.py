from __future__ import annotations

import pytest
from apoio_painel_conteudo import (
    CONTEUDO,
    SINCRONIZACAO,
    bloco_projeto,
    gravar_blocos,
    gravar_inventario,
    gravar_sugestoes,
    sugestao,
)
from apoio_painel_curriculos import gravar_versao, pasta_da_vaga
from apoio_painel_telas import AGORA, ATAQUE, CONFIG, montar

from src.painel.conteudo import RepositorioArquivosConteudo
from src.painel.curriculos import RepositorioArquivosCurriculos
from src.painel.ficticio import ConteudoFicticio, CurriculosFicticio

TEXTOS = CONFIG["textos"]["projetos"]


@pytest.fixture
def cliente():
    return montar()


def test_lista_cada_projeto_com_origem_techs_e_onde_e_usado(cliente):
    texto = cliente.get("/projetos").text
    assert "API de Pedidos (exemplo)" in texto
    assert TEXTOS["origem_github"] in texto and TEXTOS["origem_portfolio"] in texto
    assert TEXTOS["origem_guia"] in texto
    assert "Python, FastAPI, PostgreSQL" in texto
    assert 'href="/curriculos/familia/backend_pt"' in texto
    assert 'href="/curriculos/vaga/101"' in texto
    assert TEXTOS["nao_usado"] in texto
    assert TEXTOS["sem_techs"] in texto


def test_nome_de_projeto_com_tag_script_aparece_como_texto(cliente):
    texto = cliente.get("/projetos").text
    assert ATAQUE not in texto
    assert "&lt;script&gt;alert(&#x27;projeto&#x27;)&lt;/script&gt;" in texto
    assert "<img src=x" not in texto
    assert "&lt;img src=x onerror=alert(1)&gt;" in texto


def test_sugestao_com_script_no_nome_na_url_e_na_evidencia_aparece_como_texto(cliente):
    texto = cliente.get("/projetos").text
    assert "<b>descricao em negrito</b>" not in texto
    assert "&lt;b&gt;descricao em negrito&lt;/b&gt;" in texto
    assert "&lt;script&gt;alert(&#x27;sugestao&#x27;)&lt;/script&gt;" in texto
    assert "pagina:&lt;script&gt;" in texto


def test_sugestao_diz_o_efeito_antes_de_aprovar_e_pede_motivo_para_rejeitar(cliente):
    texto = cliente.get("/projetos").text
    assert TEXTOS["efeito_projeto_novo"] in texto
    assert TEXTOS["efeito_tecnologia_nova"] in texto
    assert TEXTOS["efeito_rejeitar"] in texto
    assert 'name="motivo" type="text" required' in texto
    assert 'hx-post="/sugestoes/sug_aaaaaaaaaaaa/aprovar"' in texto
    assert 'hx-post="/sugestoes/sug_aaaaaaaaaaaa/rejeitar"' in texto


def test_sem_nada_a_tela_diz_o_que_fazer():
    cliente = montar(
        curriculos=CurriculosFicticio.de_dados({}, AGORA), conteudo=ConteudoFicticio.de_dados({})
    )
    texto = cliente.get("/projetos").text
    assert TEXTOS["sem_sugestoes"] in texto
    assert TEXTOS["sem_projetos"] in texto
    lista = cliente.get("/curriculos").text
    assert CONFIG["textos"]["curriculos"]["sem_familias"] in lista


def test_arquivos_reais_mostram_projeto_origem_techs_e_uso(tmp_path):
    url = "https://github.com/ficticio/proj_alfa"
    gravar_blocos(tmp_path, [bloco_projeto("proj_alfa", "Alfa", url, "API de teste.")])
    gravar_inventario(
        tmp_path,
        [{"tech": "Python", "ancoras": [{"tipo": "projeto", "ref": "proj_alfa", "fonte": url}]}],
    )
    gravar_sugestoes(tmp_path, [sugestao("sug_a", projeto_id="proj_novo", nome="Projeto Novo")])
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    cliente = montar(
        curriculos=RepositorioArquivosCurriculos(tmp_path),
        conteudo=RepositorioArquivosConteudo(tmp_path),
    )
    texto = cliente.get("/projetos").text
    assert "Alfa" in texto and "API de teste." in texto
    assert TEXTOS["origem_github"] in texto
    assert 'href="/curriculos/vaga/7"' in texto
    assert f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>' in texto
    assert "Projeto Novo" in texto
    assert str(tmp_path) not in texto


def test_arquivos_de_conteudo_ilegiveis_viram_pagina_de_erro(tmp_path):
    pasta = tmp_path / CONTEUDO.subpasta
    pasta.mkdir(parents=True)
    (pasta / SINCRONIZACAO.arquivo_sugestoes).write_text("geradas_em: [", encoding="utf-8")
    cliente = montar(conteudo=RepositorioArquivosConteudo(tmp_path))
    resposta = cliente.get("/projetos")
    assert resposta.status_code == 503
    assert CONFIG["textos"]["erro_dados"]["titulo"] in resposta.text
