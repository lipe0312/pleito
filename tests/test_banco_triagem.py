from __future__ import annotations

import uuid

import pytest
from apoio_geracao import modelos_com_tier
from apoio_triagem import DESCRICAO_BOA, HOJE, inventario, texto_resposta

from src.coletor.contratos import ModeloTrabalho, Senioridade, VagaBruta
from src.coletor.repositorio import gravar_vagas
from src.db.conexao import conectar
from src.llm.roteador import RespostaTransporte, Roteador
from src.triagem.contratos import Motivo, codigo_do_motivo
from src.triagem.funil import executar_funil
from src.triagem.repositorio import (
    RepositorioPostgres,
    contar_descartes_por_motivo,
    listar_descartes,
)

ATAQUE = "'; DROP TABLE vaga; --"


@pytest.fixture
def lote(banco):
    sufixo = uuid.uuid4().hex[:12]
    with banco.cursor() as cursor:
        cursor.execute("SELECT COALESCE(max(id), 0) FROM pleito.uso_llm")
        uso_inicial = cursor.fetchone()[0]
    yield sufixo
    with banco.cursor() as cursor:
        cursor.execute(
            "DELETE FROM pleito.auditoria WHERE entidade = 'vaga' AND entidade_id IN "
            "(SELECT id::text FROM pleito.vaga WHERE id_externo LIKE %s)",
            (f"teste-{sufixo}%",),
        )
        cursor.execute("DELETE FROM pleito.vaga WHERE id_externo LIKE %s", (f"teste-{sufixo}%",))
        cursor.execute("DELETE FROM pleito.empresa WHERE nome_norm LIKE %s", (f"%{sufixo}%",))
        cursor.execute("DELETE FROM pleito.uso_llm WHERE id > %s", (uso_inicial,))
    banco.commit()


def _bruta(sufixo: str, indice: int, **campos) -> VagaBruta:
    base = {
        "fonte": "greenhouse",
        "id_externo": f"teste-{sufixo}-{indice}",
        "url": f"https://boards.exemplo.invalid/{sufixo}/{indice}",
        "titulo": f"Estagio em Backend {indice}",
        "empresa": f"Empresa Ficticia {indice} {sufixo}",
        "descricao": DESCRICAO_BOA,
        "local": "Remoto",
        "pais": "BR",
        "senioridade": Senioridade.ESTAGIO,
        "modelo": ModeloTrabalho.REMOTO,
        "publicada_em": HOJE,
    }
    base.update(campos)
    return VagaBruta(**base)


def _gravar_e_ids(banco, sufixo: str, vagas: list[VagaBruta]) -> list[int]:
    with conectar("app") as conexao:
        gravar_vagas(conexao, vagas)
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM pleito.vaga WHERE id_externo LIKE %s ORDER BY id", (f"teste-{sufixo}%",)
        )
        return [linha[0] for linha in cursor.fetchall()]


def _roteador(resposta: str, chamadas: list):
    def transporte(pedido):
        chamadas.append(pedido)
        return RespostaTransporte(texto=resposta, tokens_entrada=10, tokens_saida=10)

    return Roteador(
        configuracao=modelos_com_tier(True), transporte=transporte, verificar_ativo=lambda: None
    )


def _usos_do_forte(banco) -> int:
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pleito.uso_llm WHERE etapa = 'pontuacao_final' AND tier = 'forte'"
        )
        return cursor.fetchone()[0]


def _estado(banco, vaga_id: int) -> tuple:
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT estado::text, nota, motivo_descarte FROM pleito.vaga WHERE id = %s", (vaga_id,)
        )
        return cursor.fetchone()


def _funil(ids, roteador):
    from src.padroes.configuracao import configuracao_padroes
    from src.triagem.configuracao import configuracao_triagem

    with conectar("app") as conexao:
        repositorio = RepositorioPostgres(conexao, ids)
        return executar_funil(
            repositorio,
            inventario(),
            roteador,
            configuracao_triagem(),
            configuracao_padroes(),
            HOJE,
        )


def test_dia_sem_vaga_boa_nao_cria_nenhum_uso_llm_forte(banco, lote):
    ruins = [
        _bruta(lote, 1, titulo="Executivo de Vendas"),
        _bruta(lote, 2, senioridade=Senioridade.SENIOR),
        _bruta(lote, 3, descricao="Estagio generico, sem pilha informada. " * 6),
    ]
    ids = _gravar_e_ids(banco, lote, ruins)
    antes = _usos_do_forte(banco)
    chamadas: list = []

    resumo = _funil(ids, _roteador(texto_resposta(), chamadas))

    assert chamadas == []
    assert _usos_do_forte(banco) == antes
    assert resumo.chamadas_ao_modelo == 0
    motivos = [codigo_do_motivo(_estado(banco, i)[2]) for i in ids]
    assert motivos == [
        Motivo.FUNCAO.value,
        Motivo.SENIORIDADE.value,
        Motivo.PRE_NOTA.value,
    ]


def test_dia_com_uma_vaga_boa_cria_um_uso_llm_forte_e_grava_nota_estado_e_resultado(banco, lote):
    ids = _gravar_e_ids(banco, lote, [_bruta(lote, 1), _bruta(lote, 2, titulo="Gerente de Vendas")])
    antes = _usos_do_forte(banco)
    chamadas: list = []

    resumo = _funil(ids, _roteador(texto_resposta(nota_aderencia=77), chamadas))

    assert len(chamadas) == 1 and resumo.chamadas_ao_modelo == 1
    assert _usos_do_forte(banco) == antes + 1
    estado, nota, motivo = _estado(banco, ids[0])
    assert (estado, float(nota), motivo) == ("pontuada", 77.0, None)
    assert _estado(banco, ids[1])[0] == "descoberta"
    assert codigo_do_motivo(_estado(banco, ids[1])[2]) == Motivo.FUNCAO.value
    with banco.cursor() as cursor:
        cursor.execute(
            "SELECT depois FROM pleito.auditoria WHERE entidade = 'vaga' AND entidade_id = %s "
            "AND acao = 'pontuacao_final'",
            (str(ids[0]),),
        )
        depois = cursor.fetchone()[0]
    assert depois["resultado"]["nota_aderencia"] == 77
    assert depois["origem"] == "modelo"


def test_mesma_vaga_em_duas_fontes_gera_uma_chamada_e_a_copia_fica_descartada(banco, lote):
    original = _bruta(lote, 1, empresa=f"Alfa {lote}", titulo="Estagio Backend", local="Remoto")
    copia = _bruta(
        lote, 2, empresa=f"ALFA {lote}", titulo="estagio backend", local="remoto", fonte="lever"
    )
    ids = _gravar_e_ids(banco, lote, [original, copia])
    chamadas: list = []

    _funil(ids, _roteador(texto_resposta(), chamadas))

    assert len(chamadas) == 1
    assert _estado(banco, ids[1])[2] == f"{Motivo.DUPLICATA.value}: vaga {ids[0]}"


def test_vaga_vista_em_rodada_anterior_nao_e_reavaliada(banco, lote):
    ids = _gravar_e_ids(banco, lote, [_bruta(lote, 1)])
    chamadas: list = []
    roteador = _roteador(texto_resposta(), chamadas)

    _funil(ids, roteador)
    segunda = _funil(ids, roteador)

    assert len(chamadas) == 1
    assert segunda.recebidas == 0


def test_cache_por_hash_vem_da_auditoria_e_evita_nova_chamada(banco, lote):
    a, b = (
        _bruta(lote, 1, titulo="Estagio Backend"),
        _bruta(lote, 2, titulo="Estagio Backend", empresa=f"Outra {lote}"),
    )
    ids = _gravar_e_ids(banco, lote, [a, b])
    chamadas: list = []

    resumo = _funil(ids, _roteador(texto_resposta(), chamadas))

    assert len(chamadas) == 1
    assert resumo.do_cache == 1
    assert all(_estado(banco, i)[0] == "pontuada" for i in ids)


def test_descartes_sao_consultaveis_por_motivo_e_por_contagem(banco, lote):
    vagas = [
        _bruta(lote, 1, titulo="Executivo de Vendas"),
        _bruta(lote, 2, senioridade=Senioridade.SENIOR),
        _bruta(lote, 3, senioridade=Senioridade.PLENO),
    ]
    ids = _gravar_e_ids(banco, lote, vagas)

    _funil(ids, _roteador(texto_resposta(), []))

    with conectar("app") as conexao:
        seniores = listar_descartes(conexao, Motivo.SENIORIDADE.value, limite=500)
        contagem = contar_descartes_por_motivo(conexao)
    meus = [d for d in seniores if d.vaga_id in ids]
    assert {d.vaga_id for d in meus} == {ids[1], ids[2]}
    assert all(
        d.motivo == "senioridade_recusada: " + s
        for d, s in zip(sorted(meus, key=lambda d: d.vaga_id), ["senior", "pleno"], strict=True)
    )
    assert contagem[Motivo.SENIORIDADE.value] >= 2


def test_sql_no_titulo_e_na_empresa_nao_quebra_o_funil(banco, lote):
    vaga = _bruta(lote, 1, titulo=ATAQUE, empresa=f"{ATAQUE} {lote}", descricao=ATAQUE)
    ids = _gravar_e_ids(banco, lote, [vaga])

    _funil(ids, _roteador(texto_resposta(), []))

    assert codigo_do_motivo(_estado(banco, ids[0])[2]) == Motivo.FUNCAO.value
    with banco.cursor() as cursor:
        cursor.execute("SELECT to_regclass('pleito.vaga') IS NOT NULL")
        assert cursor.fetchone()[0] is True


def test_papel_da_aplicacao_nao_descarta_vaga_ja_pontuada(banco, lote):
    from src.triagem.repositorio import TransicaoRecusada

    ids = _gravar_e_ids(banco, lote, [_bruta(lote, 1)])
    _funil(ids, _roteador(texto_resposta(), []))
    assert _estado(banco, ids[0])[0] == "pontuada"

    with conectar("app") as conexao, pytest.raises(TransicaoRecusada):
        RepositorioPostgres(conexao, ids).descartar(ids[0], Motivo.PRE_NOTA.value)
