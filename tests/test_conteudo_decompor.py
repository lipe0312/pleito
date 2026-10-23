from __future__ import annotations

import dataclasses
import stat

import pytest
import yaml
from pydantic import ValidationError

from src.conteudo.__main__ import executar
from src.conteudo.arquivo import DestinoForaDeDados, gravar
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.decompor import EstruturaDivergente, GuiaInvalido, LatexProibido, decompor
from src.conteudo.modelo import (
    AncoraInvalida,
    Blocos,
    Inventario,
    ItemInventario,
    TecnologiaSemAncora,
    validar_conteudo,
)


@pytest.fixture
def config():
    return configuracao_conteudo()


@pytest.fixture
def guia(fixtures) -> str:
    return (fixtures / "guia_ficticio.md").read_text(encoding="utf-8")


def _por_id(blocos: Blocos):
    return {bloco.id: bloco for bloco in blocos.blocos}


def test_decompoe_experiencias_e_projetos_com_fatos_imutaveis(guia, config):
    blocos, _ = decompor(guia, config)
    por_id = _por_id(blocos)

    assert list(por_id) == [
        "sobre",
        "exp_empresa_exemplo_ltda",
        "exp_laboratorio_exemplo_visao",
        "proj_projeto_alfa_beta",
    ]
    estagio = por_id["exp_empresa_exemplo_ltda"]
    assert estagio.tipo == "experiencia"
    assert estagio.imutavel["cargo"] == {
        "pt": "Desenvolvedora Estagiária",
        "en": "Software Intern",
    }
    assert estagio.imutavel["periodo"]["en"] == "2023 -- Present"
    projeto = por_id["proj_projeto_alfa_beta"]
    assert projeto.imutavel["link"]["pt"] == "https://example.invalid/alfa"
    assert projeto.imutavel["descricao"] == {"pt": "sistema de exemplo", "en": "example system"}


def test_bullets_guardam_redacao_bilingue_e_techs_normalizadas(guia, config):
    blocos, _ = decompor(guia, config)
    por_id = _por_id(blocos)

    primeiro = por_id["exp_empresa_exemplo_ltda"].bullets[0]
    assert primeiro.id == "exp_empresa_exemplo_ltda_1"
    assert primeiro.techs == ["Python", "Flask", "PostgreSQL"]
    assert primeiro.redacao["en"].startswith("Built an API in \\tech{Python}")
    assert por_id["exp_laboratorio_exemplo_visao"].bullets[0].techs == ["face_recognition"]


def test_comentario_tex_nao_entra_na_redacao_e_escape_fica(guia, config):
    blocos, _ = decompor(guia, config)
    sobre = _por_id(blocos)["sobre"].redacao["pt"]

    assert "FORMAÇÃO" not in sobre
    assert sobre.endswith("100\\% fictícia.")


def test_entrada_sem_bullets_nao_vira_bloco(guia, config):
    blocos, _ = decompor(guia, config)

    assert all("mais" not in bloco.id for bloco in blocos.blocos)


def test_cabecalho_com_contato_nunca_entra_nos_blocos(guia, config):
    blocos, inventario = decompor(guia, config)
    despejo = yaml.safe_dump(blocos.model_dump()) + yaml.safe_dump(inventario.model_dump())

    assert "pessoa@exemplo.invalid" not in despejo
    assert "00000-0000" not in despejo


def test_inventario_ancora_cada_tech_nos_blocos_onde_aparece(guia, config):
    blocos, inventario = decompor(guia, config)
    por_tech = {item.tech: item for item in inventario.techs}

    assert set(por_tech) == {
        "Python",
        "Flask",
        "PostgreSQL",
        "RabbitMQ",
        "face_recognition",
        "Docker Compose",
    }
    assert [ancora.ref for ancora in por_tech["PostgreSQL"].ancoras] == [
        "exp_empresa_exemplo_ltda",
        "proj_projeto_alfa_beta",
    ]
    assert por_tech["Docker Compose"].ancoras[0].tipo == "projeto"
    validar_conteudo(blocos, inventario)


def test_inventario_traz_as_equivalencias_honestas_do_guia(guia, config):
    _, inventario = decompor(guia, config)

    assert [(e.pedido, e.tem) for e in inventario.equivalencias] == [
        ("Kubernetes", "Docker Compose"),
        ("Kafka", "RabbitMQ"),
    ]
    assert inventario.equivalencias[1].citar == "cite mensageria assíncrona e eventos"


def test_sobre_com_tech_sem_ancora_em_bullet_e_recusado(guia, config):
    inventado = guia.replace(
        "Estudante de exemplo com \\tech{Python}",
        "Estudante de exemplo com \\tech{Kubernetes} e \\tech{Python}",
    )

    with pytest.raises(TecnologiaSemAncora, match="Kubernetes"):
        decompor(inventado, config)


def test_tech_de_bullet_fora_do_inventario_e_recusada(guia, config):
    blocos, inventario = decompor(guia, config)
    sem_flask = Inventario(
        techs=[item for item in inventario.techs if item.tech != "Flask"],
        equivalencias=inventario.equivalencias,
    )

    with pytest.raises(TecnologiaSemAncora, match="Flask"):
        validar_conteudo(blocos, sem_flask)


def test_ancora_para_bloco_inexistente_e_recusada(guia, config):
    blocos, inventario = decompor(guia, config)
    item = inventario.techs[0].model_dump()
    item["ancoras"][0]["ref"] = "proj_que_nao_existe"
    alterado = Inventario(
        techs=[ItemInventario.model_validate(item), *inventario.techs[1:]],
        equivalencias=inventario.equivalencias,
    )

    with pytest.raises(AncoraInvalida, match="proj_que_nao_existe"):
        validar_conteudo(blocos, alterado)


def test_schema_recusa_tech_sem_ancora_e_campo_desconhecido():
    with pytest.raises(ValidationError):
        ItemInventario.model_validate({"tech": "Java", "ancoras": []})
    with pytest.raises(ValidationError):
        ItemInventario.model_validate(
            {
                "tech": "Java",
                "ancoras": [{"tipo": "projeto", "ref": "proj_x", "fonte": "guia"}],
                "nivel": "senior",
            }
        )


def test_schema_recusa_id_duplicado_e_idioma_faltando(guia, config):
    blocos, _ = decompor(guia, config)
    bruto = blocos.model_dump()

    duplicado = {**bruto, "blocos": [*bruto["blocos"], bruto["blocos"][1]]}
    with pytest.raises(ValidationError, match="duplicado"):
        Blocos.model_validate(duplicado)

    sem_ingles = blocos.model_dump()
    sem_ingles["blocos"][1]["bullets"][0]["redacao"].pop("en")
    with pytest.raises(ValidationError, match="idiomas"):
        Blocos.model_validate(sem_ingles)


def test_versoes_com_estrutura_diferente_sao_recusadas(guia, config):
    divergente = guia.replace(
        "\\item Maintained queues with \\tech{RabbitMQ}.\n", "", 1
    )

    with pytest.raises(EstruturaDivergente):
        decompor(divergente, config)


def test_guia_sem_curriculo_base_e_recusado(config):
    with pytest.raises(GuiaInvalido):
        decompor("# Guia\n\n## 1. Papel\n\nnada aqui\n", config)


def test_grava_so_dentro_de_dados_e_sem_permissao_para_outros(guia, config, tmp_path):
    blocos, inventario = decompor(guia, config)
    pasta_dados = tmp_path / "dados"

    caminho_blocos, caminho_inventario = gravar(blocos, inventario, pasta_dados, config)

    assert caminho_blocos.parent == pasta_dados / "conteudo"
    assert Blocos.model_validate(yaml.safe_load(caminho_blocos.read_text(encoding="utf-8")))
    assert Inventario.model_validate(
        yaml.safe_load(caminho_inventario.read_text(encoding="utf-8"))
    )
    assert stat.S_IMODE(caminho_blocos.stat().st_mode) == 0o600


@pytest.mark.parametrize("subpasta", ["../config", "/var/fora", "conteudo/../../x"])
def test_destino_fora_de_dados_e_recusado(guia, config, tmp_path, subpasta):
    blocos, inventario = decompor(guia, config)
    fora = dataclasses.replace(config, subpasta=subpasta)

    with pytest.raises(DestinoForaDeDados):
        gravar(blocos, inventario, tmp_path / "dados", fora)


def test_config_versionada_grava_dentro_de_dados(config):
    assert not config.subpasta.startswith(("/", ".."))
    assert ".." not in config.subpasta.split("/")


def test_comando_le_o_guia_de_pleito_guia(fixtures, tmp_path, capsys):
    pasta_dados = tmp_path / "dados"
    codigo = executar(
        {"PLEITO_GUIA": str(fixtures / "guia_ficticio.md")}, pasta_dados, tmp_path
    )

    assert codigo == 0
    assert (pasta_dados / "conteudo" / "blocos.yaml").is_file()
    assert "4 blocos" in capsys.readouterr().out


def test_comando_resolve_pleito_guia_relativo_a_raiz(fixtures, tmp_path):
    codigo = executar({"PLEITO_GUIA": "fixtures/guia_ficticio.md"}, tmp_path / "d", fixtures.parent)

    assert codigo == 0


def test_comando_sem_pleito_guia_falha_sem_gravar(tmp_path, capsys):
    codigo = executar({}, tmp_path / "dados", tmp_path)

    assert codigo != 0
    assert "PLEITO_GUIA" in capsys.readouterr().err
    assert not (tmp_path / "dados").exists()


def test_comando_com_guia_inexistente_falha(tmp_path, capsys):
    codigo = executar({"PLEITO_GUIA": str(tmp_path / "nao.md")}, tmp_path / "dados", tmp_path)

    assert codigo != 0
    assert not (tmp_path / "dados").exists()


def test_comando_com_invencao_no_guia_falha_sem_gravar(guia, tmp_path, capsys):
    inventado = tmp_path / "guia.md"
    inventado.write_text(
        guia.replace("com \\tech{Python} e \\tech{PostgreSQL},", "com \\tech{Rust},"),
        encoding="utf-8",
    )

    codigo = executar({"PLEITO_GUIA": str(inventado)}, tmp_path / "dados", tmp_path)

    assert codigo != 0
    assert "Rust" in capsys.readouterr().err
    assert not (tmp_path / "dados").exists()


@pytest.mark.parametrize("campo", ["arquivo_blocos", "arquivo_inventario"])
def test_nome_de_arquivo_com_caminho_e_recusado(guia, config, tmp_path, campo):
    blocos, inventario = decompor(guia, config)
    fora = dataclasses.replace(config, **{campo: "../../x.yaml"})

    with pytest.raises(DestinoForaDeDados):
        gravar(blocos, inventario, tmp_path / "dados", fora)
    assert not (tmp_path / "x.yaml").exists()


@pytest.mark.parametrize("subpasta", ["", "."])
def test_destino_na_raiz_de_dados_e_recusado(guia, config, tmp_path, subpasta):
    blocos, inventario = decompor(guia, config)
    raiz = dataclasses.replace(config, subpasta=subpasta)

    with pytest.raises(DestinoForaDeDados):
        gravar(blocos, inventario, tmp_path / "dados", raiz)


def test_symlink_em_dados_apontando_para_fora_e_recusado(guia, config, tmp_path):
    blocos, inventario = decompor(guia, config)
    fora = tmp_path / "fora"
    fora.mkdir()
    pasta_dados = tmp_path / "dados"
    pasta_dados.mkdir()
    (pasta_dados / config.subpasta).symlink_to(fora, target_is_directory=True)

    with pytest.raises(DestinoForaDeDados):
        gravar(blocos, inventario, pasta_dados, config)
    assert list(fora.iterdir()) == []


def test_pasta_existente_fica_so_para_o_dono(guia, config, tmp_path):
    blocos, inventario = decompor(guia, config)
    destino = tmp_path / "dados" / config.subpasta
    destino.mkdir(parents=True)
    destino.chmod(0o755)

    _, caminho_inventario = gravar(blocos, inventario, tmp_path / "dados", config)

    assert stat.S_IMODE(destino.stat().st_mode) == 0o700
    assert stat.S_IMODE(caminho_inventario.stat().st_mode) == 0o600


def test_temporario_symlink_nao_e_seguido(guia, config, tmp_path):
    blocos, inventario = decompor(guia, config)
    alvo = tmp_path / "alvo.txt"
    alvo.write_text("intacto", encoding="utf-8")
    destino = tmp_path / "dados" / config.subpasta
    destino.mkdir(parents=True)
    (destino / f".{config.arquivo_blocos}.tmp").symlink_to(alvo)

    gravar(blocos, inventario, tmp_path / "dados", config)

    assert alvo.read_text(encoding="utf-8") == "intacto"
    assert not (destino / config.arquivo_blocos).is_symlink()


def test_falha_na_escrita_nao_deixa_temporario(guia, config, tmp_path, monkeypatch):
    blocos, inventario = decompor(guia, config)

    def falhar(*_):
        raise OSError("disco cheio")

    monkeypatch.setattr("src.conteudo.arquivo.os.replace", falhar)
    with pytest.raises(OSError, match="disco cheio"):
        gravar(blocos, inventario, tmp_path / "dados", config)

    assert list((tmp_path / "dados" / config.subpasta).iterdir()) == []


ATAQUES_LATEX = [
    "\\input{/etc/passwd}",
    "\\include{segredo}",
    "\\immediate\\write18{curl exemplo.invalid}",
    "\\openout\\arquivo=saida.tex",
    "\\catcode`\\^=7",
    "^^5cinput{/etc/passwd}",
]


@pytest.mark.parametrize("ataque", ATAQUES_LATEX)
@pytest.mark.parametrize(
    "alvo",
    [
        "Mantive filas com \\tech{RabbitMQ}.",
        "Estudante de exemplo com",
        "sistema de exemplo",
        "Pesquisadora, Laboratório Exemplo",
        "2023 -- Presente",
    ],
)
def test_latex_fora_da_allowlist_e_recusado(guia, config, ataque, alvo):
    envenenado = guia.replace(alvo, f"{alvo} {ataque}", 1)
    assert envenenado != guia

    with pytest.raises(LatexProibido):
        decompor(envenenado, config)


def test_comando_com_latex_malicioso_falha_sem_gravar(guia, tmp_path, capsys):
    envenenado = tmp_path / "guia.md"
    envenenado.write_text(
        guia.replace("Mantive filas", "\\input{/etc/passwd} Mantive filas"), encoding="utf-8"
    )

    codigo = executar({"PLEITO_GUIA": str(envenenado)}, tmp_path / "dados", tmp_path)

    assert codigo != 0
    assert "input" in capsys.readouterr().err
    assert not (tmp_path / "dados").exists()
