from __future__ import annotations

import shutil

import pytest
from apoio_gerador import PASTA_FIXTURES
from apoio_laco import BLOCOS, INVENTARIO, roteador_em_sequencia, vaga, validos

from src.conteudo.arquivo import destino_conteudo, gravar
from src.conteudo.configuracao import configuracao_conteudo
from src.gerador.__main__ import executar, pasta_da_vaga
from src.gerador.configuracao import configuracao_gerador


@pytest.fixture
def dados(tmp_path):
    conteudo = configuracao_conteudo()
    gravar(BLOCOS, INVENTARIO, tmp_path, conteudo)
    shutil.copyfile(
        PASTA_FIXTURES / "travado_ficticio.yaml",
        destino_conteudo(tmp_path, conteudo) / configuracao_gerador().travado.arquivo,
    )
    return tmp_path


def _executar(argv, pasta_dados, rastro_roteador=None):
    roteador, rastro = roteador_em_sequencia([validos()])
    pendencias = []
    codigo = executar(
        argv,
        pasta_dados,
        lambda _vaga_id: vaga(),
        lambda: roteador,
        lambda *dados: pendencias.append(dados),
    )
    return codigo, rastro, pendencias


def test_geracao_sem_familia_e_idioma_e_recusada_antes_de_qualquer_chamada(dados, capsys):
    codigo, rastro, _ = _executar(["--vaga", "7"], dados)

    assert codigo == 2
    assert rastro.pedidos == []
    assert "--familia" in capsys.readouterr().err


def test_refacao_sem_versao_anterior_e_recusada_sem_chamar(dados, capsys):
    codigo, rastro, _ = _executar(
        ["--vaga", "7", "--familia", "backend_arquitetura", "--idioma", "pt", "--refazer", "x"],
        dados,
    )

    assert codigo == 2
    assert rastro.pedidos == []
    assert "refacao recusada" in capsys.readouterr().err
    assert not (pasta_da_vaga(dados, 7, configuracao_gerador()) / "tentativas").exists()


def test_vaga_fica_na_pasta_de_vagas_dos_dados(dados):
    pasta = pasta_da_vaga(dados, 7, configuracao_gerador())

    assert pasta.relative_to(dados).parts == (configuracao_gerador().laco.pasta_vagas, "7")
