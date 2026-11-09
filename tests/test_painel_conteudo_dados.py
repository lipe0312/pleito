from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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

from src.conteudo.arquivo import ler_blocos, ler_inventario
from src.conteudo.sugestoes import carregar_sugestoes
from src.painel.conteudo import DecisaoRecusada, RepositorioArquivosConteudo

AGORA = datetime(2026, 11, 6, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
URL = "https://github.com/ficticio/proj_alfa"


@pytest.fixture
def repositorio(tmp_path):
    return RepositorioArquivosConteudo(tmp_path)


def decisao(tmp_path, ident):
    sugestoes = carregar_sugestoes(tmp_path, CONTEUDO, SINCRONIZACAO)
    return next(s for s in sugestoes.sugestoes if s.id == ident)


def test_projeto_traz_nome_descricao_e_techs_ancoradas_no_projeto(tmp_path, repositorio):
    gravar_blocos(tmp_path, [bloco_projeto("proj_alfa", "Alfa", URL, "API de teste.")])
    gravar_inventario(
        tmp_path,
        [
            {"tech": "Python", "ancoras": [{"tipo": "projeto", "ref": "proj_alfa", "fonte": URL}]},
            {"tech": "Java", "ancoras": [{"tipo": "disciplina", "ref": "poo", "fonte": "guia"}]},
        ],
    )
    [projeto] = repositorio.projetos()
    assert (projeto.nome, projeto.descricao) == ("Alfa", "API de teste.")
    assert projeto.techs == ("Python",)


def test_origem_do_projeto_vem_da_sugestao_aprovada_ou_do_dominio_do_link(tmp_path, repositorio):
    gravar_blocos(
        tmp_path,
        [
            bloco_projeto("proj_alfa", "Alfa", URL),
            bloco_projeto("proj_beta", "Beta", "https://exemplo.invalid/beta"),
            bloco_projeto("proj_gama", "Gama", "https://exemplo.invalid/gama"),
        ],
    )
    gravar_sugestoes(
        tmp_path,
        [sugestao("sug_1", projeto_id="proj_beta", origem="portfolio", status="aprovada")],
    )
    origens = {p.id: p.origem for p in repositorio.projetos()}
    assert origens == {"proj_alfa": "github", "proj_beta": "portfolio", "proj_gama": "guia"}


def test_link_so_e_clicavel_quando_https_e_de_dominio_conhecido(tmp_path, repositorio):
    gravar_blocos(
        tmp_path,
        [
            bloco_projeto("proj_alfa", "Alfa", URL),
            bloco_projeto("proj_beta", "Beta", "javascript:alert(1)"),
            bloco_projeto("proj_gama", "Gama", "https://estranho.invalid/x"),
        ],
    )
    clicaveis = {p.id: p.link_clicavel for p in repositorio.projetos()}
    assert clicaveis == {"proj_alfa": True, "proj_beta": False, "proj_gama": False}


def test_sem_arquivos_de_conteudo_as_listas_sao_vazias(repositorio):
    assert repositorio.projetos() == []
    assert repositorio.sugestoes_pendentes() == []


def test_so_as_sugestoes_pendentes_aparecem(tmp_path, repositorio):
    gravar_sugestoes(
        tmp_path,
        [sugestao("sug_a"), sugestao("sug_b", status="rejeitada", projeto_id="proj_b")],
    )
    assert [s.id for s in repositorio.sugestoes_pendentes()] == ["sug_a"]


def test_aprovar_grava_o_bloco_quem_aprovou_e_quando(tmp_path, repositorio):
    gravar_sugestoes(tmp_path, [sugestao("sug_a", nome="Projeto Novo", projeto_id="proj_novo")])
    repositorio.aprovar("sug_a", "Fulano", AGORA)
    registro = decisao(tmp_path, "sug_a")
    assert registro.status == "aprovada"
    assert registro.decidida_por == "Fulano"
    assert registro.decidida_em == AGORA.isoformat()
    assert [b.id for b in ler_blocos(tmp_path, CONTEUDO).blocos] == ["proj_novo"]
    assert repositorio.sugestoes_pendentes() == []


def test_aprovar_tecnologia_sem_o_projeto_aprovado_e_recusado_sem_escrever(tmp_path, repositorio):
    gravar_blocos(tmp_path, [bloco_projeto("proj_alfa", "Alfa", URL)])
    gravar_sugestoes(
        tmp_path,
        [sugestao("sug_t", tipo="tecnologia_nova", projeto_id="proj_novo", tech="Docker")],
    )
    with pytest.raises(DecisaoRecusada) as erro:
        repositorio.aprovar("sug_t", "Fulano", AGORA)
    assert erro.value.chave == "projeto_nao_aprovado"
    assert decisao(tmp_path, "sug_t").status == "pendente"
    assert ler_inventario(tmp_path, CONTEUDO) is None


def test_rejeitar_grava_o_motivo_e_quem_rejeitou(tmp_path, repositorio):
    gravar_sugestoes(tmp_path, [sugestao("sug_a")])
    repositorio.rejeitar("sug_a", "Fulano", "projeto de disciplina", AGORA)
    registro = decisao(tmp_path, "sug_a")
    assert (registro.status, registro.motivo) == ("rejeitada", "projeto de disciplina")
    assert registro.decidida_por == "Fulano"
    assert registro.decidida_em == AGORA.isoformat()


@pytest.mark.parametrize("motivo", ["", "   ", "\n\t"])
def test_rejeitar_sem_motivo_e_recusado_e_nada_muda(tmp_path, repositorio, motivo):
    gravar_sugestoes(tmp_path, [sugestao("sug_a")])
    with pytest.raises(DecisaoRecusada) as erro:
        repositorio.rejeitar("sug_a", "Fulano", motivo, AGORA)
    assert erro.value.chave == "motivo_vazio"
    assert decisao(tmp_path, "sug_a").status == "pendente"


def test_sugestao_inexistente_e_ja_decidida_tem_chave_propria(tmp_path, repositorio):
    gravar_sugestoes(tmp_path, [sugestao("sug_a", status="aprovada")])
    with pytest.raises(DecisaoRecusada) as inexistente:
        repositorio.aprovar("sug_zzz", "Fulano", AGORA)
    with pytest.raises(DecisaoRecusada) as decidida:
        repositorio.aprovar("sug_a", "Fulano", AGORA)
    assert inexistente.value.chave == "inexistente"
    assert decidida.value.chave == "ja_decidida"
