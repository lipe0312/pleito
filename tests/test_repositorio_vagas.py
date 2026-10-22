from __future__ import annotations

import pytest

from src.coletor.contratos import VagaBruta
from src.coletor.repositorio import (
    FonteDesconhecida,
    ResumoGravacao,
    chave_deduplicacao,
    deduplicar_lote,
    gravar_vagas,
)

ATAQUE = "'; DROP TABLE vagas; --"


def _vaga(**campos) -> VagaBruta:
    base = {
        "fonte": "greenhouse",
        "id_externo": "1",
        "url": "https://boards.greenhouse.io/empresaficticia/jobs/1",
        "titulo": "Estagio em Dados",
        "empresa": "Empresa Ficticia",
        "descricao": "descricao ficticia",
        "local": "Sao Paulo",
    }
    base.update(campos)
    return VagaBruta(**base)


def _chamadas(conexao: ConexaoFalsa, inicio: str) -> list[tuple[str, tuple]]:
    return [(s, p) for s, p in conexao.chamadas if " ".join(s.split()).upper().startswith(inicio)]


class CursorFalso:
    def __init__(self, conexao: ConexaoFalsa) -> None:
        self._conexao = conexao
        self._resposta: tuple | None = None

    def __enter__(self) -> CursorFalso:
        return self

    def __exit__(self, *args) -> None:
        return None

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._conexao.chamadas.append((sql, params))
        texto = " ".join(sql.split()).upper()
        if texto.startswith("SELECT ID FROM FONTE"):
            self._resposta = (3,) if params[0] in self._conexao.fontes else None
        elif texto.startswith("SELECT ID FROM EMPRESA"):
            self._resposta = (7,)
        elif texto.startswith("INSERT INTO VAGA"):
            self._resposta = (99,) if self._conexao.aceita_insercao else None
        else:
            self._resposta = None

    def fetchone(self) -> tuple | None:
        return self._resposta


class ConexaoFalsa:
    def __init__(self, fontes=("greenhouse",), aceita_insercao=True) -> None:
        self.chamadas: list[tuple[str, tuple]] = []
        self.fontes = fontes
        self.aceita_insercao = aceita_insercao

    def cursor(self) -> CursorFalso:
        return CursorFalso(self)


def test_chave_ignora_caixa_e_espacos_da_empresa():
    a = _vaga(empresa="Empresa Ficticia")
    b = _vaga(empresa="  empresa ficticia ")
    assert chave_deduplicacao(a)[:2] == chave_deduplicacao(b)[:2]


def test_chave_muda_com_fonte_empresa_e_conteudo():
    base = _vaga()
    assert chave_deduplicacao(base) != chave_deduplicacao(_vaga(fonte="lever"))
    assert chave_deduplicacao(base) != chave_deduplicacao(_vaga(empresa="Outra Ficticia"))
    assert chave_deduplicacao(base) != chave_deduplicacao(_vaga(descricao="outro texto"))


def test_lote_com_mesma_vaga_duas_vezes_fica_com_uma():
    primeira = _vaga(id_externo="1")
    repetida = _vaga(id_externo="2")
    outra = _vaga(id_externo="3", titulo="Estagio em Backend")
    assert deduplicar_lote([primeira, repetida, outra]) == [primeira, outra]


def test_mesma_vaga_em_fontes_diferentes_nao_e_duplicata_do_lote():
    assert len(deduplicar_lote([_vaga(), _vaga(fonte="lever")])) == 2


def test_gravacao_conta_inseridas_e_duplicadas():
    conexao = ConexaoFalsa()
    resumo = gravar_vagas(conexao, [_vaga(id_externo="1"), _vaga(id_externo="2")])
    assert resumo == ResumoGravacao(recebidas=2, inseridas=1, duplicadas=1)


def test_gravacao_contra_banco_que_ja_tem_a_vaga_conta_duplicada():
    conexao = ConexaoFalsa(aceita_insercao=False)
    resumo = gravar_vagas(conexao, [_vaga()])
    assert resumo == ResumoGravacao(recebidas=1, inseridas=0, duplicadas=1)


def test_fonte_sem_linha_no_banco_e_recusada_sem_inserir():
    conexao = ConexaoFalsa(fontes=())
    with pytest.raises(FonteDesconhecida):
        gravar_vagas(conexao, [_vaga()])
    assert not _chamadas(conexao, "INSERT INTO VAGA")


def test_sql_em_titulo_e_empresa_vai_como_parametro_nunca_no_texto_do_sql():
    conexao = ConexaoFalsa()
    gravar_vagas(conexao, [_vaga(titulo=ATAQUE, empresa=ATAQUE, descricao=ATAQUE, local=ATAQUE)])
    assert conexao.chamadas
    for sql, _ in conexao.chamadas:
        assert "DROP" not in sql.upper()
        assert ATAQUE not in sql
    parametros = [p for _, params in conexao.chamadas for p in params]
    assert ATAQUE in parametros


def test_sem_empresa_grava_sem_criar_empresa():
    conexao = ConexaoFalsa()
    gravar_vagas(conexao, [_vaga(empresa="")])
    assert not _chamadas(conexao, "INSERT INTO EMPRESA")
    assert _chamadas(conexao, "INSERT INTO VAGA")[0][1][1] is None
