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
