from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from apoio_validador import conteudo_rico

from src.conteudo.arquivo import gravar
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.modelo import Ancora
from src.conteudo.sincronizacao import configuracao_sincronizacao
from src.conteudo.sugestoes import ProjetoSugerido, Sugestao, Sugestoes, gravar_sugestoes
from src.validador import dados
from src.validador.banco import BancoTecnologias, montar_banco
from src.validador.configuracao import configuracao_validador
from src.validador.vocabulario import Vocabulario, montar_vocabulario

CONFIG = configuracao_validador()


def _sugestao(tech, evidencias, status="aprovada", projeto="proj_repositorio_ficticio"):
    return Sugestao(
        id=f"sug_{tech.lower()}",
        tipo="tecnologia_nova",
        status=status,
        origem="github",
        projeto=ProjetoSugerido(
            id=projeto, nome="Repositorio Ficticio", url="https://example.invalid/repo"
        ),
        tech=tech,
        ancora=Ancora(tipo="projeto", ref=projeto, fonte="https://example.invalid/repo"),
        evidencias=evidencias,
        vista_em="2026-01-01",
    )


def _sugestoes(*itens):
    return Sugestoes(geradas_em="2026-01-01", sugestoes=list(itens))


def test_banco_traz_cada_tecnologia_do_inventario_com_a_fonte_de_cada_ancora():
    _, inventario = conteudo_rico()

    banco = montar_banco(inventario, None)

    por_nome = {t.tech: t for t in banco.tecnologias}
    assert set(por_nome) == {item.tech for item in inventario.techs}
    for item in inventario.techs:
        evidencias = por_nome[item.tech].evidencias
        assert [e.origem for e in evidencias] == ["inventario"] * len(item.ancoras)
        assert [e.fonte for e in evidencias] == [a.fonte for a in item.ancoras]
        assert [e.ref for e in evidencias] == [f"{a.tipo}:{a.ref}" for a in item.ancoras]


def test_banco_junta_as_ancoras_do_f27_com_origem_e_fonte_publica():
    _, inventario = conteudo_rico()
    sugestoes = _sugestoes(
        _sugestao("Docker", ["linguagem:Dockerfile", "topic:docker", "readme:Docker Compose"])
    )

    banco = montar_banco(inventario, sugestoes)

    docker = next(t for t in banco.tecnologias if t.tech == "Docker")
    assert [e.origem for e in docker.evidencias] == ["linguagem", "topic", "readme"]
    assert {e.fonte for e in docker.evidencias} == {"https://example.invalid/repo"}
    assert {e.ref for e in docker.evidencias} == {"proj_repositorio_ficticio"}


@pytest.mark.parametrize("status", ["pendente", "rejeitada"])
def test_so_sugestao_aprovada_vira_evidencia(status):
    _, inventario = conteudo_rico()
    sugestoes = _sugestoes(_sugestao("Docker", ["topic:docker"], status=status))

    banco = montar_banco(inventario, sugestoes)

    assert banco.evidencias_de("Docker") == []


def test_sugestao_pendente_nao_salva_tecnologia_em_texto_puro():
    from apoio_validador import inventario_ficticio, tex_com_corpo

    from src.validador.resultado import Regra
    from src.validador.validar import validar_fonte

    inventario = inventario_ficticio()
    banco = montar_banco(inventario, _sugestoes(_sugestao("Kafka", ["topic:kafka"], "pendente")))

    resultado = validar_fonte(tex_com_corpo("Experiência com Kafka"), inventario, banco=banco)

    assert Regra.TECNOLOGIA in resultado.regras_bloqueadas


def test_sugestao_rejeitada_nao_vira_evidencia():
    _, inventario = conteudo_rico()
    sugestoes = _sugestoes(_sugestao("Docker", ["topic:docker"], status="rejeitada"))

    banco = montar_banco(inventario, sugestoes)

    assert "Docker" not in {t.tech for t in banco.tecnologias}


def test_sugestao_sem_marca_de_evidencia_nao_prova_nada():
    _, inventario = conteudo_rico()

    banco = montar_banco(inventario, _sugestoes(_sugestao("Docker", [])))

    assert "Docker" not in {t.tech for t in banco.tecnologias}


def test_evidencias_da_mesma_tecnologia_em_caixa_diferente_se_juntam():
    _, inventario = conteudo_rico()
    sugestoes = _sugestoes(_sugestao("PYTHON", ["linguagem:Python"]))

    banco = montar_banco(inventario, sugestoes)

    assert [t.tech for t in banco.tecnologias].count("Python") == 1
    python = next(t for t in banco.tecnologias if t.tech == "Python")
    assert "linguagem" in {e.origem for e in python.evidencias}


def test_busca_de_evidencia_ignora_caixa():
    _, inventario = conteudo_rico()
    banco = montar_banco(inventario, None)

    assert banco.evidencias_de("python") == banco.evidencias_de("PYTHON") != []
    assert banco.evidencias_de("Cobol") == []


def test_vocabulario_separa_pt_e_en_com_verbos_siglas_termos_e_projetos():
    blocos, _ = conteudo_rico()

    vocabulario = montar_vocabulario(blocos, CONFIG)

    assert set(vocabulario.root) == {"pt", "en"}
    pt, en = vocabulario.root["pt"], vocabulario.root["en"]
    assert "construi" in pt.verbos and "mantive" in pt.verbos
    assert "maintained" in en.verbos and "mantive" not in en.verbos
    assert "api" in pt.siglas
    assert "projeto alfa beta" in pt.projetos
    assert "projeto gama" in pt.projetos
    assert any(" " in termo for termo in pt.termos)
    assert "hardware de borda" in pt.termos


def test_vocabulario_nao_guarda_sigla_nem_termo_com_tecnologia_do_dicionario():
    blocos, _ = conteudo_rico()
    base = blocos.blocos[1]
    texto = {
        "pt": "Integrei API Kafka com Docker Swarm e KAFKA em hardware de borda.",
        "en": "Integrated API Kafka with Docker Swarm and KAFKA on edge hardware.",
    }
    bullet = base.bullets[0].model_copy(update={"redacao": texto})
    alterado = base.model_copy(update={"bullets": [bullet, *base.bullets[1:]]})
    novos = blocos.model_copy(update={"blocos": [blocos.blocos[0], alterado, *blocos.blocos[2:]]})

    vocabulario = montar_vocabulario(novos, CONFIG)

    for idioma, termos in vocabulario.root.items():
        guardados = [*termos.siglas, *termos.termos, *termos.projetos]
        assert guardados, idioma
        assert not any("kafka" in t or "docker" in t for t in guardados), idioma
    assert "api" in vocabulario.root["pt"].siglas


def test_termos_de_dominio_nao_comecam_nem_terminam_em_palavra_vazia():
    blocos, _ = conteudo_rico()
    vocabulario = montar_vocabulario(blocos, CONFIG)
    vazias = set(CONFIG.conteudo.idioma.marcadores["pt"])

    for termo in vocabulario.root["pt"].termos:
        palavras = termo.split()
        assert palavras[0] not in vazias and palavras[-1] not in vazias


def test_ngrama_maximo_vem_da_configuracao():
    from apoio_validador import configuracao_com

    blocos, _ = conteudo_rico()
    config = configuracao_com(dados__vocabulario__ngrama_max=2)

    termos = montar_vocabulario(blocos, config).root["pt"].termos

    assert termos and max(len(t.split()) for t in termos) <= 2


def test_gerar_dados_grava_banco_e_vocabulario_em_dados_com_permissao_restrita(tmp_path):
    blocos, inventario = conteudo_rico()
    conteudo = configuracao_conteudo()
    gravar(blocos, inventario, tmp_path, conteudo)
    sinc = configuracao_sincronizacao()
    gravar_sugestoes(_sugestoes(_sugestao("Docker", ["topic:docker"])), tmp_path, conteudo, sinc)

    codigo = dados.executar(tmp_path)

    pasta = tmp_path / conteudo.subpasta
    assert codigo == 0
    banco_arquivo = pasta / CONFIG.dados.arquivos.tecnologias
    vocabulario_arquivo = pasta / CONFIG.dados.arquivos.vocabulario
    assert banco_arquivo.stat().st_mode & 0o777 == 0o600
    assert vocabulario_arquivo.stat().st_mode & 0o777 == 0o600
    banco = dados.carregar_banco(tmp_path)
    vocabulario = dados.carregar_vocabulario(tmp_path)
    assert isinstance(banco, BancoTecnologias) and isinstance(vocabulario, Vocabulario)
    assert banco.evidencias_de("Docker")
    assert set(yaml.safe_load(vocabulario_arquivo.read_text(encoding="utf-8"))) == {"pt", "en"}


def test_gerar_dados_sem_blocos_pede_o_make_conteudo_antes(tmp_path, capsys):
    codigo = dados.executar(tmp_path)

    assert codigo == 2
    assert "make conteudo" in capsys.readouterr().err
    assert dados.carregar_banco(tmp_path) is None
    assert dados.carregar_vocabulario(tmp_path) is None


def test_gerar_dados_sem_sugestoes_usa_so_o_inventario(tmp_path):
    blocos, inventario = conteudo_rico()
    gravar(blocos, inventario, tmp_path, configuracao_conteudo())

    assert dados.executar(tmp_path) == 0
    assert dados.carregar_banco(tmp_path).evidencias_de("Python")


def test_arquivos_gerados_ficam_dentro_de_dados(tmp_path):
    caminho = dados.caminho_do_banco(tmp_path)

    assert caminho.resolve().is_relative_to(tmp_path.resolve())


def test_nome_de_arquivo_com_caminho_na_configuracao_e_recusado():
    from apoio_validador import configuracao_com
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        configuracao_com(dados__arquivos={"tecnologias": "../fora.yaml", "vocabulario": "v.yaml"})


def test_dados_gerados_nunca_sao_versionados():
    raiz = Path(__file__).resolve().parent.parent
    ignorados = (raiz / ".gitignore").read_text(encoding="utf-8").split()

    assert "dados/" in ignorados
    assert CONFIG.dados.arquivos.tecnologias.startswith(("tecnologias",))
    assert not list(raiz.glob("config/**/tecnologias.yaml"))
    assert not list(raiz.glob("config/**/vocabulario.yaml"))
