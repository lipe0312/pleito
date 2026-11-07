from __future__ import annotations

from apoio_triagem import vaga

from src.triagem.configuracao import configuracao_triagem
from src.triagem.deduplicacao import Deduplicador
from src.triagem.normalizacao import chave_da_vaga, normalizar, url_canonica

CONFIG = configuracao_triagem()


def test_normalizar_tira_acento_caixa_e_pontuacao():
    assert normalizar("  Estágio  em  Análise-de-Dados! ") == "estagio em analise de dados"


def test_url_canonica_remove_rastreio_e_fragmento_e_mantem_o_id_da_vaga():
    suja = "HTTPS://www.Exemplo.invalid/vagas/10/?utm_source=x&gh_jid=77&ref=y#topo"
    limpa = "https://exemplo.invalid/vagas/10?gh_jid=77"
    assert url_canonica(suja, CONFIG.normalizacao) == limpa


def test_mesma_vaga_com_caixa_e_acento_diferentes_tem_a_mesma_chave():
    a = vaga(1, empresa="Açaí Tech", titulo="Estágio Backend", local="Salvador, BA")
    b = vaga(2, empresa="acai tech", titulo="ESTAGIO  BACKEND", local="salvador ba", fonte="lever")
    assert chave_da_vaga(a, CONFIG.normalizacao).hash == chave_da_vaga(b, CONFIG.normalizacao).hash


def test_empresa_diferente_muda_a_chave():
    a = vaga(1, empresa="Alfa", titulo="Estagio", local="SP")
    b = vaga(2, empresa="Beta", titulo="Estagio", local="SP")
    assert chave_da_vaga(a, CONFIG.normalizacao).hash != chave_da_vaga(b, CONFIG.normalizacao).hash


def test_mesma_vaga_em_duas_fontes_e_duplicata_pela_empresa_titulo_e_local():
    dedup = Deduplicador(CONFIG.normalizacao)
    original = vaga(1, empresa="Alfa", titulo="Estagio Backend", local="SP", fonte="greenhouse")
    copia = vaga(
        2,
        empresa="ALFA",
        titulo="estagio backend",
        local="sp",
        fonte="lever",
        url="https://outro.invalid/9",
    )
    dedup.registrar(original)
    assert dedup.duplicada_de(copia) == 1


def test_mesma_url_canonica_com_titulo_diferente_e_duplicata():
    dedup = Deduplicador(CONFIG.normalizacao)
    dedup.registrar(vaga(1, empresa="Alfa", titulo="Estagio A", url="https://x.invalid/v/1"))
    outra = vaga(
        2, empresa="Beta", titulo="Estagio B", url="https://www.x.invalid/v/1?utm_medium=z"
    )
    assert dedup.duplicada_de(outra) == 1


def test_vagas_distintas_nao_sao_duplicata():
    dedup = Deduplicador(CONFIG.normalizacao)
    dedup.registrar(vaga(1))
    assert dedup.duplicada_de(vaga(2)) is None


def test_empresa_vazia_nao_junta_vagas_de_titulo_igual():
    dedup = Deduplicador(CONFIG.normalizacao)
    dedup.registrar(vaga(1, empresa="", titulo="Estagio", local="SP", url="https://a.invalid/1"))
    assert (
        dedup.duplicada_de(
            vaga(2, empresa="", titulo="Estagio", local="SP", url="https://b.invalid/2")
        )
        is None
    )
