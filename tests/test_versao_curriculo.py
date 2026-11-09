from __future__ import annotations

import re
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb

from src.db.versao_curriculo import (
    NovaVersao,
    Origem,
    RegistroVersao,
    historico_da_vaga,
    registrar_versao,
)

MIGRACAO = Path("db/migrations/0005_versao_curriculo.sql")


class CursorFalso:
    def __init__(self, linhas):
        self.linhas = linhas
        self.executados = []

    def __enter__(self):
        return self

    def __exit__(self, *argumentos):
        return False

    def execute(self, comando, parametros=()):
        self.executados.append((comando, parametros))

    def fetchone(self):
        return self.linhas[0]

    def fetchall(self):
        return self.linhas


class ConexaoFalsa:
    def __init__(self, linhas):
        self.cursor_falso = CursorFalso(linhas)

    def cursor(self):
        return self.cursor_falso


def _nova(**campos) -> NovaVersao:
    base = {
        "vaga_id": 7,
        "familia": "dados",
        "idioma": "pt",
        "caminho_tex": "dados/vagas/7/cv.tex",
        "caminho_pdf": "dados/vagas/7/cv.pdf",
        "hash_pdf": b"\x01" * 32,
        "paginas": 1,
        "linhas_livres": None,
        "validacao": {"aprovado": True},
        "prompt_versao": "gerar_slots-v1",
        "modelo": "modelo-x",
        "origem": Origem.GERADA,
    }
    return NovaVersao(**(base | campos))


def test_origens_do_modulo_sao_as_do_enum_da_migration():
    texto = MIGRACAO.read_text(encoding="utf-8")
    achado = re.search(r"CREATE TYPE origem_versao AS ENUM \(([^)]*)\)", texto)
    assert achado
    valores = set(re.findall(r"'([a-z_]+)'", achado.group(1)))
    assert valores == {origem.value for origem in Origem}
    assert {origem.value for origem in Origem} == {"gerada", "refeita", "chat"}


def test_registrar_versao_usa_parametros_e_devolve_id_e_numero():
    conexao = ConexaoFalsa([(11, 4)])
    registro = registrar_versao(conexao, _nova(origem=Origem.CHAT))
    assert registro == RegistroVersao(id=11, numero=4)
    comando, parametros = conexao.cursor_falso.executados[0]
    assert "INSERT INTO versao_curriculo" in comando
    assert "7" not in comando and "dados/vagas" not in comando
    assert "chat" in parametros
    assert any(isinstance(item, Jsonb) for item in parametros)
    assert b"\x01" * 32 in parametros


def test_registrar_versao_recusa_origem_desconhecida_antes_de_tocar_no_banco():
    conexao = ConexaoFalsa([(1, 1)])
    with pytest.raises(ValueError):
        registrar_versao(conexao, _nova(origem="manual"))
    assert conexao.cursor_falso.executados == []


def test_registrar_versao_recusa_hash_que_nao_e_sha256():
    conexao = ConexaoFalsa([(1, 1)])
    with pytest.raises(ValueError):
        registrar_versao(conexao, _nova(hash_pdf=b"curto"))
    assert conexao.cursor_falso.executados == []


def test_historico_da_vaga_converte_as_linhas_em_registros():
    linha = (
        3,
        2,
        "base",
        Origem.REFEITA.value,
        b"\x02" * 32,
        "p-v1",
        "m-x",
        "dados/vagas/7/cv.pdf",
        {"aprovado": True},
        1,
        "2026-01-01",
        True,
        False,
    )
    conexao = ConexaoFalsa([linha])
    (versao,) = historico_da_vaga(conexao, 7)
    assert (versao.id, versao.numero, versao.origem, versao.aprovada, versao.enviada) == (
        3,
        2,
        Origem.REFEITA,
        True,
        False,
    )
    comando, parametros = conexao.cursor_falso.executados[0]
    assert "historico_versao_curriculo" in comando
    assert parametros == (7,)


def test_migration_e_aditiva_e_nao_apaga_nem_recria_tabela_aplicada():
    texto = MIGRACAO.read_text(encoding="utf-8").upper()
    for proibido in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"):
        assert proibido not in texto
    assert "CREATE TABLE VERSAO_CURRICULO" not in texto
