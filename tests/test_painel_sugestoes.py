from __future__ import annotations

import pytest
from apoio_painel_conteudo import (
    CONTEUDO,
    SINCRONIZACAO,
    gravar_blocos,
    gravar_sugestoes,
    sugestao,
)
from apoio_painel_curriculos import gravar_versao, pasta_da_vaga
from apoio_painel_telas import (
    AGORA,
    CABECALHO,
    CONFIG,
    FIXTURE,
    com_token,
    montar,
    token_da_pagina,
)

from src.conteudo.arquivo import ler_blocos
from src.conteudo.sugestoes import carregar_sugestoes
from src.painel.conteudo import RepositorioArquivosConteudo
from src.painel.curriculos import RepositorioArquivosCurriculos
from src.painel.ficticio import ConteudoFicticio

TEXTOS = CONFIG["textos"]["projetos"]
ROTA_APROVAR = "/sugestoes/sug_aaaaaaaaaaaa/aprovar"
ROTA_REJEITAR = "/sugestoes/sug_aaaaaaaaaaaa/rejeitar"
QUANDO = "05/11 18:00"


@pytest.fixture
def conteudo():
    return ConteudoFicticio.de_arquivo(FIXTURE)


@pytest.fixture
def cliente(conteudo):
    return montar(conteudo=conteudo)


def rejeitar(cliente, motivo, **extra):
    return cliente.post(
        ROTA_REJEITAR,
        content=f"motivo={motivo}".encode(),
        headers={**com_token(cliente), "content-type": "application/x-www-form-urlencoded"},
        **extra,
    )


@pytest.mark.parametrize("rota", [ROTA_APROVAR, ROTA_REJEITAR])
def test_post_sem_token_csrf_e_recusado_e_nada_muda(cliente, conteudo, rota):
    resposta = cliente.post(rota, content=b"motivo=qualquer")
    assert resposta.status_code == 403
    assert conteudo.decididas == {}
    assert "sug_aaaaaaaaaaaa" in {s.id for s in conteudo.sugestoes_pendentes()}


@pytest.mark.parametrize("rota", [ROTA_APROVAR, ROTA_REJEITAR])
def test_post_com_token_errado_e_recusado(cliente, conteudo, rota):
    token = token_da_pagina(cliente)
    resposta = cliente.post(rota, content=b"motivo=x", headers={CABECALHO: token[::-1]})
    assert resposta.status_code == 403
    assert conteudo.decididas == {}


def test_post_com_token_certo_mas_origem_de_fora_e_recusado(cliente, conteudo):
    resposta = cliente.post(
        ROTA_APROVAR, headers={**com_token(cliente), "origin": "http://evil.example"}
    )
    assert resposta.status_code == 403
    assert conteudo.decididas == {}


def test_get_nao_decide_nada(cliente, conteudo):
    assert cliente.get(ROTA_APROVAR).status_code == 405
    assert conteudo.decididas == {}


def test_aprovar_registra_quem_e_quando_e_devolve_o_item_decidido(cliente, conteudo):
    resposta = cliente.post(ROTA_APROVAR, headers=com_token(cliente))
    assert resposta.status_code == 200
    assert TEXTOS["aprovada"].format(por=CONFIG["aprovador"], quando=QUANDO) in resposta.text
    registro = conteudo.decididas["sug_aaaaaaaaaaaa"]
    assert registro["status"] == "aprovada"
    assert registro["por"] == CONFIG["aprovador"]
    assert registro["em"] == AGORA
    assert "sug_aaaaaaaaaaaa" not in {s.id for s in conteudo.sugestoes_pendentes()}


def test_rejeitar_com_motivo_grava_o_motivo_e_escapa_na_resposta(cliente, conteudo):
    resposta = rejeitar(cliente, "%3Cscript%3Ealert(1)%3C%2Fscript%3E+de+disciplina")
    assert resposta.status_code == 200
    assert "<script>alert(1)" not in resposta.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt; de disciplina" in resposta.text
    registro = conteudo.decididas["sug_aaaaaaaaaaaa"]
    assert registro["status"] == "rejeitada"
    assert registro["motivo"] == "<script>alert(1)</script> de disciplina"
    assert registro["por"] == CONFIG["aprovador"]


@pytest.mark.parametrize("corpo", [b"", b"motivo=", b"motivo=+++", b"outro=campo"])
def test_rejeitar_sem_motivo_e_recusada_e_a_sugestao_continua_pendente(cliente, conteudo, corpo):
    resposta = cliente.post(
        ROTA_REJEITAR,
        content=corpo,
        headers={**com_token(cliente), "content-type": "application/x-www-form-urlencoded"},
    )
    assert resposta.status_code == 422
    assert TEXTOS["erros"]["motivo_vazio"] in resposta.text
    assert 'name="motivo"' in resposta.text
    assert conteudo.decididas == {}


def test_rejeitar_com_motivo_acima_do_limite_e_recusada(cliente, conteudo):
    resposta = rejeitar(cliente, "a" * (CONFIG["motivo_max_chars"] + 1))
    assert resposta.status_code == 422
    assert conteudo.decididas == {}


def test_corpo_acima_do_limite_e_recusado_antes_de_ler_tudo(cliente, conteudo):
    resposta = rejeitar(cliente, "a" * (CONFIG["corpo_max_bytes"] + 1))
    assert resposta.status_code == 413
    assert conteudo.decididas == {}


def test_decidir_duas_vezes_e_recusado_e_decidir_o_que_nao_existe_tambem(cliente, conteudo):
    cliente.post(ROTA_APROVAR, headers=com_token(cliente))
    segunda = cliente.post(ROTA_APROVAR, headers=com_token(cliente))
    inexistente = cliente.post("/sugestoes/sug_nada/aprovar", headers=com_token(cliente))
    assert segunda.status_code == 409
    assert TEXTOS["erros"]["ja_decidida"] in segunda.text
    assert inexistente.status_code == 404
    assert TEXTOS["erros"]["inexistente"] in inexistente.text
    assert len(conteudo.decididas) == 1


def test_id_com_html_na_rota_nao_vira_html_na_resposta(cliente):
    resposta = cliente.post("/sugestoes/%3Cscript%3E/aprovar", headers=com_token(cliente))
    assert "<script>" not in resposta.text


def test_o_navegador_troca_o_item_nas_respostas_de_erro_do_formulario(cliente):
    pagina = cliente.get("/projetos").text
    assert "responseHandling" in pagina
    assert "^(404|409|422)$" in pagina
    status = set(CONFIG["status_da_decisao"].values())
    assert status == {404, 409, 422}


def preparar_arquivos(tmp_path, sugestoes):
    gravar_sugestoes(tmp_path, sugestoes)
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    return montar(
        curriculos=RepositorioArquivosCurriculos(tmp_path),
        conteudo=RepositorioArquivosConteudo(tmp_path),
    )


def registro(tmp_path, ident):
    sugestoes = carregar_sugestoes(tmp_path, CONTEUDO, SINCRONIZACAO)
    return next(s for s in sugestoes.sugestoes if s.id == ident)


def test_arquivos_reais_aprovar_grava_quem_quando_e_o_bloco(tmp_path):
    cliente = preparar_arquivos(tmp_path, [sugestao("sug_a", projeto_id="proj_novo")])
    resposta = cliente.post("/sugestoes/sug_a/aprovar", headers=com_token(cliente))
    assert resposta.status_code == 200
    decidida = registro(tmp_path, "sug_a")
    assert decidida.status == "aprovada"
    assert decidida.decidida_por == CONFIG["aprovador"]
    assert decidida.decidida_em == AGORA.isoformat()
    assert [b.id for b in ler_blocos(tmp_path, CONTEUDO).blocos] == ["proj_novo"]


def test_arquivos_reais_post_sem_token_nao_toca_nos_arquivos(tmp_path):
    cliente = preparar_arquivos(tmp_path, [sugestao("sug_a", projeto_id="proj_novo")])
    antes = (tmp_path / CONTEUDO.subpasta / SINCRONIZACAO.arquivo_sugestoes).read_bytes()
    assert cliente.post("/sugestoes/sug_a/aprovar").status_code == 403
    assert cliente.post("/sugestoes/sug_a/rejeitar", content=b"motivo=x").status_code == 403
    depois = (tmp_path / CONTEUDO.subpasta / SINCRONIZACAO.arquivo_sugestoes).read_bytes()
    assert antes == depois
    assert ler_blocos(tmp_path, CONTEUDO) is None


def test_arquivos_reais_rejeitar_grava_motivo_e_nao_cria_bloco(tmp_path):
    cliente = preparar_arquivos(tmp_path, [sugestao("sug_a", projeto_id="proj_novo")])
    resposta = cliente.post(
        "/sugestoes/sug_a/rejeitar",
        content=b"motivo=projeto+de+disciplina",
        headers={**com_token(cliente), "content-type": "application/x-www-form-urlencoded"},
    )
    assert resposta.status_code == 200
    decidida = registro(tmp_path, "sug_a")
    assert (decidida.status, decidida.motivo) == ("rejeitada", "projeto de disciplina")
    assert ler_blocos(tmp_path, CONTEUDO) is None


def test_arquivos_reais_tecnologia_sem_projeto_aprovado_volta_409_com_a_instrucao(tmp_path):
    gravar_blocos(tmp_path, [])
    cliente = preparar_arquivos(
        tmp_path,
        [sugestao("sug_t", tipo="tecnologia_nova", projeto_id="proj_novo", tech="Docker")],
    )
    resposta = cliente.post("/sugestoes/sug_t/aprovar", headers=com_token(cliente))
    assert resposta.status_code == 409
    assert TEXTOS["erros"]["projeto_nao_aprovado"] in resposta.text
    assert registro(tmp_path, "sug_t").status == "pendente"
