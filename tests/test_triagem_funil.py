from __future__ import annotations

import pytest
from apoio_geracao import roteador_falso
from apoio_triagem import (
    DESCRICAO_BOA,
    HOJE,
    RepositorioMemoria,
    inventario,
    texto_resposta,
    vaga,
)

from src.coletor.contratos import Senioridade
from src.triagem.configuracao import configuracao_triagem
from src.triagem.contratos import Motivo, TransicaoRecusada, VagaTriagem, codigo_do_motivo
from src.triagem.funil import executar_funil

CONFIG = configuracao_triagem()
INVENTARIO = inventario()
MAXIMO = CONFIG.pre_pontuadas_max


def _funil(repositorio, roteador):
    return executar_funil(repositorio, INVENTARIO, roteador, hoje=HOJE)


def _lote_de_50() -> list[VagaTriagem]:
    boas = [vaga(i, descricao=DESCRICAO_BOA) for i in (1, 2, 3)]
    area_errada = [
        vaga(i, titulo=f"Executivo de Vendas {i}", descricao="x" * 300) for i in range(4, 14)
    ]
    senior = [vaga(i, senioridade=Senioridade.SENIOR) for i in range(14, 24)]
    sem_pilha = [
        vaga(i, titulo=f"Estagio em Dados {i}", descricao="Estagio generico, sem pilha. " * 10)
        for i in range(24, 34)
    ]
    exigentes = [
        vaga(
            i,
            titulo=f"Desenvolvedor Backend {i}",
            url=f"https://z.invalid/{i}",
            descricao="Pede 6 anos de experiencia em Python. " * 6,
        )
        for i in range(34, 44)
    ]
    copias = [
        vaga(
            i,
            empresa=f"Empresa Ficticia {(i - 44) % 3 + 1}",
            titulo=f"Estagio em Backend {(i - 44) % 3 + 1}",
            fonte="lever",
            url=f"https://outra.invalid/{i}",
        )
        for i in range(44, 51)
    ]
    return [*boas, *area_errada, *senior, *sem_pilha, *exigentes, *copias]


def test_lote_de_50_vagas_com_3_boas_faz_no_maximo_o_limite_de_chamadas_fortes():
    lote = _lote_de_50()
    assert len(lote) == 50
    repositorio = RepositorioMemoria(lote)
    roteador, rastro = roteador_falso(texto_resposta())

    resumo = _funil(repositorio, roteador)

    assert len(rastro.reservas) <= MAXIMO
    assert len(rastro.reservas) == 3
    assert set(repositorio.pontuadas) == {1, 2, 3}
    assert resumo.chamadas_ao_modelo == 3
    assert resumo.recebidas == 50
    assert resumo.duplicadas == 7


def test_todo_descarte_tem_motivo_gravado_e_toda_vaga_tem_destino():
    repositorio = RepositorioMemoria(_lote_de_50())
    roteador, _ = roteador_falso(texto_resposta())

    _funil(repositorio, roteador)

    destinos = (
        set(repositorio.descartes) | set(repositorio.pontuadas) | set(repositorio.aguardando_lista)
    )
    assert destinos == {v.id for v in repositorio.pendentes_lista}
    assert all(motivo.strip() for motivo in repositorio.descartes.values())
    codigos = {codigo_do_motivo(m) for m in repositorio.descartes.values()}
    assert codigos <= {m.value for m in Motivo}
    assert {Motivo.DUPLICATA, Motivo.FUNCAO, Motivo.SENIORIDADE, Motivo.PRE_NOTA, Motivo.ANOS} <= {
        Motivo(c) for c in codigos
    }


def test_dia_sem_vaga_boa_gera_zero_chamada_forte():
    ruins = [v for v in _lote_de_50() if v.id > 3 and v.id < 44]
    repositorio = RepositorioMemoria(ruins)
    roteador, rastro = roteador_falso(texto_resposta())

    resumo = _funil(repositorio, roteador)

    assert rastro.reservas == [] and rastro.pedidos == []
    assert resumo.chamadas_ao_modelo == 0
    assert repositorio.pontuadas == {}
    assert len(repositorio.descartes) == len(ruins)


def test_lote_vazio_nao_chama_o_modelo():
    roteador, rastro = roteador_falso(texto_resposta())
    resumo = _funil(RepositorioMemoria([]), roteador)
    assert rastro.reservas == []
    assert resumo.recebidas == 0


def test_mesma_vaga_em_duas_fontes_e_avaliada_uma_vez():
    original = vaga(1, empresa="Alfa", titulo="Estagio Backend", local="Remoto")
    copia = vaga(
        2,
        empresa="ALFA",
        titulo="estagio backend",
        local="remoto",
        fonte="lever",
        url="https://outra.invalid/2",
    )
    repositorio = RepositorioMemoria([original, copia])
    roteador, rastro = roteador_falso(texto_resposta())

    _funil(repositorio, roteador)

    assert len(rastro.reservas) == 1
    assert set(repositorio.pontuadas) == {1}
    assert repositorio.descartes[2] == f"{Motivo.DUPLICATA.value}: vaga 1"


def test_duplicata_de_vaga_ja_vista_em_outro_dia_nao_e_reavaliada():
    antiga = vaga(1, empresa="Alfa", titulo="Estagio Backend", local="Remoto")
    nova = vaga(
        2,
        empresa="Alfa",
        titulo="Estagio Backend",
        local="Remoto",
        fonte="lever",
        url="https://outra.invalid/2",
    )
    repositorio = RepositorioMemoria([nova])
    repositorio.vistas_lista.append(antiga)
    roteador, rastro = roteador_falso(texto_resposta())

    _funil(repositorio, roteador)

    assert rastro.reservas == []
    assert codigo_do_motivo(repositorio.descartes[2]) == Motivo.DUPLICATA.value


def test_vaga_vista_nunca_e_reavaliada_em_nova_rodada():
    repositorio = RepositorioMemoria(_lote_de_50())
    roteador, rastro = roteador_falso(texto_resposta())
    _funil(repositorio, roteador)
    chamadas = len(rastro.reservas)

    segunda = _funil(repositorio, roteador)

    assert len(rastro.reservas) == chamadas
    assert segunda.recebidas == 0 and segunda.chamadas_ao_modelo == 0


def test_so_as_melhores_ate_o_limite_vao_ao_modelo_e_o_resto_espera_o_dia_seguinte():
    boas = [vaga(i, empresa=f"Alfa {i}", titulo=f"Estagio Backend {i}") for i in range(1, 21)]
    repositorio = RepositorioMemoria(boas)
    roteador, rastro = roteador_falso(texto_resposta())

    resumo = _funil(repositorio, roteador)

    assert len(rastro.reservas) == MAXIMO
    assert len(repositorio.pontuadas) == MAXIMO
    assert len(repositorio.aguardando()) == 20 - MAXIMO
    assert resumo.aguardando == 20 - MAXIMO

    _funil(repositorio, roteador)

    assert len(rastro.reservas) == 20
    assert repositorio.aguardando() == []


def test_as_de_maior_pre_nota_vao_primeiro():
    comuns = [vaga(i, empresa=f"Alfa {i}", titulo=f"Estagio Backend {i}") for i in range(1, 21)]
    alvo = vaga(99, empresa="Alvo", titulo="Estagio Backend Alvo", alvo=True)
    repositorio = RepositorioMemoria([*comuns, alvo])
    roteador, _ = roteador_falso(texto_resposta())

    _funil(repositorio, roteador)

    assert 99 in repositorio.pontuadas


def test_pre_nota_abaixo_do_minimo_nao_vai_ao_modelo_e_grava_a_nota():
    fraca = vaga(1, descricao="Estagio generico, sem pilha informada. " * 6)
    repositorio = RepositorioMemoria([fraca])
    roteador, rastro = roteador_falso(texto_resposta())

    _funil(repositorio, roteador)

    assert rastro.reservas == []
    assert repositorio.descartes[1].startswith(Motivo.PRE_NOTA.value)
    assert repositorio.notas_de_descarte[1] < CONFIG.pre_nota_minima


def test_resposta_invalida_descarta_com_motivo_e_nao_tenta_de_novo():
    repositorio = RepositorioMemoria([vaga(1)])
    roteador, rastro = roteador_falso(texto_resposta(familia="hacker"))

    _funil(repositorio, roteador)
    _funil(repositorio, roteador)

    assert repositorio.descartes[1].startswith(Motivo.PONTUACAO_INVALIDA.value)
    assert len(rastro.reservas) == 1
    assert repositorio.pontuadas == {}


def test_modelo_desabilitado_adia_sem_descartar_e_sem_gastar():
    segunda = vaga(2, empresa="Beta", titulo="Estagio Desenvolvedor")
    repositorio = RepositorioMemoria([vaga(1), segunda])
    roteador, rastro = roteador_falso(texto_resposta(), habilitado=False)

    resumo = _funil(repositorio, roteador)

    assert rastro.reservas == []
    assert repositorio.descartes == {}
    assert len(repositorio.aguardando()) == 2
    assert resumo.adiadas == 2


def test_orcamento_esgotado_para_a_rodada_e_deixa_o_resto_aguardando():
    from src.llm.orcamento import OrcamentoEsgotado

    chamadas = []

    def reserva():
        if chamadas:
            raise OrcamentoEsgotado("teto do dia")
        chamadas.append(1)

    boas = [vaga(i, empresa=f"Alfa {i}", titulo=f"Estagio Backend {i}") for i in range(1, 6)]
    repositorio = RepositorioMemoria(boas)
    roteador, _ = roteador_falso(texto_resposta(), reserva=reserva)

    resumo = _funil(repositorio, roteador)

    assert len(repositorio.pontuadas) == 1
    assert repositorio.descartes == {}
    assert resumo.adiadas == 4


def test_cache_por_hash_evita_segunda_chamada_para_o_mesmo_texto():
    a = vaga(1, empresa="Alfa", titulo="Estagio Backend", local="Remoto")
    b = vaga(2, empresa="Beta", titulo="Estagio Backend", local="Remoto")
    repositorio = RepositorioMemoria([a, b])
    roteador, rastro = roteador_falso(texto_resposta())

    resumo = _funil(repositorio, roteador)

    assert len(rastro.reservas) == 1
    assert set(repositorio.pontuadas) == {1, 2}
    assert repositorio.origens == {1: "modelo", 2: "cache"}
    assert resumo.do_cache == 1 and resumo.chamadas_ao_modelo == 1


def test_sistema_desativado_propaga_depois_de_gravar_a_parte_deterministica():
    from src.db.flags import SistemaDesativado

    def desligado():
        raise SistemaDesativado("flag")

    repositorio = RepositorioMemoria([vaga(1), vaga(2, titulo="Executivo de Vendas")])
    roteador, _ = roteador_falso(texto_resposta(), ativo=desligado)

    with pytest.raises(SistemaDesativado):
        _funil(repositorio, roteador)

    assert 2 in repositorio.descartes
    assert 1 in repositorio.aguardando_lista


def test_erro_transitorio_do_provedor_deixa_a_vaga_aguardando_e_segue_para_a_proxima():
    from src.llm.roteador import Roteador

    chamadas = []

    def transporte(pedido):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise ValueError("provedor recusou a solicitacao")
        from src.llm.roteador import RespostaTransporte

        return RespostaTransporte(texto=texto_resposta(), tokens_entrada=1, tokens_saida=1)

    from apoio_geracao import modelos_com_tier

    roteador = Roteador(
        configuracao=modelos_com_tier(True),
        transporte=transporte,
        reservar=lambda **dados: 1,
        finalizar=lambda *args: None,
        falhar=lambda *args: None,
        verificar_ativo=lambda: None,
    )
    repositorio = RepositorioMemoria(
        [vaga(1, titulo="Estagio Backend A"), vaga(2, titulo="Estagio Backend B")]
    )

    resumo = _funil(repositorio, roteador)

    assert 1 not in repositorio.descartes
    assert [item.vaga.id for item in repositorio.aguardando()] == [1]
    assert set(repositorio.pontuadas) == {2}
    assert resumo.adiadas == 1 and resumo.invalidas == 0


class RepositorioQueRecusa(RepositorioMemoria):
    def __init__(self, vagas, recusadas):
        super().__init__(vagas)
        self.recusadas = recusadas

    def descartar(self, vaga_id, motivo, nota=None):
        if vaga_id in self.recusadas:
            raise TransicaoRecusada("estado mudou")
        super().descartar(vaga_id, motivo, nota)

    def triar(self, vaga_id, pre_nota):
        if vaga_id in self.recusadas:
            raise TransicaoRecusada("estado mudou")
        super().triar(vaga_id, pre_nota)


def test_transicao_recusada_numa_vaga_nao_desfaz_o_lote():
    lote = [
        vaga(1, titulo="Executivo de Vendas"),
        vaga(2, titulo="Estagio Backend B"),
        vaga(3, titulo="Gerente Comercial"),
        vaga(4, titulo="Estagio Backend D"),
    ]
    repositorio = RepositorioQueRecusa(lote, recusadas={1, 2})
    roteador, rastro = roteador_falso(texto_resposta())

    resumo = _funil(repositorio, roteador)

    assert resumo.transicoes_recusadas == 2
    assert 3 in repositorio.descartes
    assert set(repositorio.pontuadas) == {4}
    assert 1 not in repositorio.descartes and 2 not in repositorio.aguardando_lista


def test_transicao_recusada_ao_pontuar_nao_para_a_rodada():
    class Recusa(RepositorioMemoria):
        def pontuar(self, vaga_id, nota, registro, origem):
            if vaga_id == 1:
                raise TransicaoRecusada("estado mudou")
            super().pontuar(vaga_id, nota, registro, origem)

    repositorio = Recusa([vaga(1, titulo="Estagio Backend A"), vaga(2, titulo="Estagio Backend B")])
    roteador, _ = roteador_falso(texto_resposta())

    resumo = _funil(repositorio, roteador)

    assert set(repositorio.pontuadas) == {2}
    assert resumo.transicoes_recusadas == 1
