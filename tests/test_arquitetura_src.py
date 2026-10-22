from __future__ import annotations

import ast
from pathlib import Path


def test_src_nao_depende_de_viabilidade():
    violacoes = []
    for caminho in Path("src").rglob("*.py"):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes = [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes = [no.module]
            else:
                continue
            if any(nome == "viabilidade" or nome.startswith("viabilidade.") for nome in nomes):
                violacoes.append(str(caminho))
    assert not violacoes


def test_configuracao_compartilhada_tem_modulo_em_src():
    assert Path("src/config.py").is_file()


def test_modulos_definitivos_nao_sao_apenas_reexportadores():
    caminhos = (
        Path("src/coletor/contratos.py"),
        Path("src/coletor/conformidade.py"),
        Path("src/triagem/regra.py"),
        Path("src/email/remetente.py"),
        Path("src/email/classificador.py"),
    )
    for caminho in caminhos:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        assert any(isinstance(no, (ast.FunctionDef, ast.ClassDef)) for no in arvore.body)


def test_compatibilidade_do_spike_reexporta_as_implementacoes_definitivas():
    from src.coletor.conformidade import consultar_robots as consultar_src
    from src.coletor.contratos import VagaBruta as VagaBrutaSrc
    from src.config import carregar as carregar_src
    from src.triagem.regra import inferir_funcao as inferir_src
    from viabilidade.config import carregar as carregar_viabilidade
    from viabilidade.conformidade import consultar_robots as consultar_viabilidade
    from viabilidade.contratos import VagaBruta as VagaBrutaViabilidade
    from viabilidade.triagem import inferir_funcao as inferir_viabilidade

    assert carregar_src is carregar_viabilidade
    assert consultar_src is consultar_viabilidade
    assert VagaBrutaSrc is VagaBrutaViabilidade
    assert inferir_src is inferir_viabilidade


def test_ingest_do_spike_so_reexporta_sem_logica():
    for caminho in Path("viabilidade/ingest").glob("*.py"):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        definicoes = [
            no for no in arvore.body if isinstance(no, (ast.FunctionDef, ast.ClassDef, ast.Assign))
        ]
        atribuicoes = [
            no for no in definicoes if isinstance(no, ast.Assign) and no.targets[0].id != "__all__"
        ]
        funcoes_ou_classes = [no for no in definicoes if not isinstance(no, ast.Assign)]
        assert not funcoes_ou_classes and not atribuicoes, str(caminho)


def test_coletores_do_spike_sao_os_mesmos_objetos_de_src():
    from src.coletor.base import ColetorHttp as ColetorSrc
    from src.coletor.base import registro as registro_src
    from src.coletor.greenhouse import FonteGreenhouse as GreenhouseSrc
    from viabilidade.ingest import FonteGreenhouse as GreenhouseSpike
    from viabilidade.ingest.base import ColetorHttp as ColetorSpike
    from viabilidade.ingest.base import registro as registro_spike

    assert ColetorSrc is ColetorSpike
    assert GreenhouseSrc is GreenhouseSpike
    assert registro_src() == registro_spike()
    assert "greenhouse" in registro_spike()


def test_spike_de_alertas_usa_o_verificador_de_remetente_de_src():
    from src.coletor import email_alertas as definitivo_alertas
    from src.email.remetente import remetente_confiavel as definitivo
    from viabilidade.ingest import email_alertas

    assert definitivo_alertas.remetente_confiavel_src is definitivo
    assert email_alertas.remetente_confiavel is definitivo_alertas.remetente_confiavel
    assert email_alertas.remetente_confiavel("jobs-noreply@linkedin.com")
    assert not email_alertas.remetente_confiavel("no-reply@gupy.com.br")
