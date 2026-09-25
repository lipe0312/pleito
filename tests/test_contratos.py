from __future__ import annotations

import pytest

from viabilidade.contratos import (
    ModeloTrabalho,
    MotivoNoGo,
    ResultadoColeta,
    Senioridade,
    VagaBruta,
    Veredito,
)


def test_url_http_e_rejeitada():
    with pytest.raises(ValueError, match="https"):
        VagaBruta(
            fonte="x",
            id_externo="1",
            url="http://exemplo.com/v/1",
            titulo="Dev",
            empresa="X",
        )


def test_id_externo_vazio_e_rejeitado():
    with pytest.raises(ValueError, match="id_externo"):
        VagaBruta(fonte="x", id_externo="", url="https://a.com/1", titulo="Dev", empresa="X")


def test_hash_ignora_url_e_pega_conteudo(vaga_completa):
    outra = VagaBruta(
        fonte="lever",
        id_externo="999",
        url="https://jobs.lever.co/x/999",
        titulo=vaga_completa.titulo,
        empresa=vaga_completa.empresa,
        descricao=vaga_completa.descricao,
        local=vaga_completa.local,
    )
    assert outra.hash_conteudo == vaga_completa.hash_conteudo


def test_completude_total_quando_campos_presentes(vaga_completa):
    assert vaga_completa.campos_ausentes == ()
    assert vaga_completa.completude == 1.0


def test_descricao_curta_conta_como_ausente():
    vaga = VagaBruta(
        fonte="x",
        id_externo="1",
        url="https://a.com/1",
        titulo="Dev",
        empresa="X",
        descricao="curta",
        local="Salvador",
        senioridade=Senioridade.JUNIOR,
        modelo=ModeloTrabalho.REMOTO,
    )
    assert "descricao" in vaga.campos_ausentes


def test_robots_proibido_forca_no_go(vaga_completa):
    r = ResultadoColeta(fonte="gupy", vagas=[vaga_completa], robots_permite=False)
    assert r.veredito() is Veredito.NO_GO


def test_motivo_registrado_forca_no_go(vaga_completa):
    r = ResultadoColeta(
        fonte="gupy", vagas=[vaga_completa] * 10, motivos=[MotivoNoGo.EXIGE_LOGIN]
    )
    assert r.veredito() is Veredito.NO_GO


def test_poucas_vagas_gera_ressalva(vaga_completa):
    r = ResultadoColeta(fonte="ashby", vagas=[vaga_completa], robots_permite=True)
    assert r.veredito() is Veredito.GO_COM_RESSALVA


def test_tos_pendente_nunca_e_go_pleno(vaga_completa):
    r = ResultadoColeta(
        fonte="gupy", vagas=[vaga_completa] * 10, robots_permite=True, requer_revisao_tos=True
    )
    assert r.veredito() is Veredito.GO_COM_RESSALVA


def test_go_pleno_com_volume_e_completude(vaga_completa):
    r = ResultadoColeta(fonte="greenhouse", vagas=[vaga_completa] * 10, robots_permite=True)
    assert r.veredito() is Veredito.GO
