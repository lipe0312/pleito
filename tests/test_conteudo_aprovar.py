from __future__ import annotations

from datetime import UTC, datetime

import pytest
import respx
import yaml
from apoio_sincronizacao import AGORA, REPO_URL, montar_github, repositorio, rodar

from src.conteudo import aprovar as aprovar_modulo
from src.conteudo.aprovar import (
    JaDecidida,
    ProjetoNaoAprovado,
    SugestaoInexistente,
    aprovar,
    executar,
    rejeitar,
)
from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.modelo import Blocos, Inventario, validar_conteudo
from src.conteudo.sincronizacao import configuracao_sincronizacao
from src.conteudo.sugestoes import carregar_sugestoes

PASTA = "conteudo"
DEPOIS = datetime(2030, 1, 11, 9, 30, tzinfo=UTC)
ID_PROJETO = "proj_ficticio_api"


@pytest.fixture
def pasta(tmp_path):
    with respx.mock(assert_all_called=False) as roteador:
        montar_github(roteador, [repositorio()], {"ficticio-api": {"Java": 1}}, {})
        rodar(tmp_path)
    return tmp_path


def _id(pasta_dados, tipo, tech=None) -> str:
    sugestoes = carregar_sugestoes(
        pasta_dados, configuracao_conteudo(), configuracao_sincronizacao()
    )
    return next(s.id for s in sugestoes.sugestoes if s.tipo == tipo and s.tech == tech)


def _aprovar(pasta_dados, sugestao_id, por="Filipe", agora=DEPOIS):
    return aprovar(
        sugestao_id, por, agora, pasta_dados, configuracao_conteudo(), configuracao_sincronizacao()
    )


def _blocos(pasta_dados) -> Blocos:
    texto = (pasta_dados / PASTA / "blocos.yaml").read_text(encoding="utf-8")
    return Blocos.model_validate(yaml.safe_load(texto))


def _inventario(pasta_dados) -> Inventario:
    texto = (pasta_dados / PASTA / "inventario.yaml").read_text(encoding="utf-8")
    return Inventario.model_validate(yaml.safe_load(texto))


def test_aprovar_projeto_novo_grava_o_bloco_e_registra_quem_e_quando(pasta):
    decidida = _aprovar(pasta, _id(pasta, "projeto_novo"))

    bloco = _blocos(pasta).blocos[0]
    assert (bloco.id, bloco.tipo) == (ID_PROJETO, "projeto")
    assert bloco.imutavel["link"] == {
        "pt": f"{REPO_URL}/ficticio-api",
        "en": f"{REPO_URL}/ficticio-api",
    }
    assert bloco.imutavel["nome"]["pt"] == "ficticio-api"
    assert (decidida.status, decidida.decidida_por) == ("aprovada", "Filipe")
    assert decidida.decidida_em == DEPOIS.isoformat()
    gravada = next(
        s
        for s in carregar_sugestoes(
            pasta, configuracao_conteudo(), configuracao_sincronizacao()
        ).sugestoes
        if s.id == decidida.id
    )
    assert (gravada.status, gravada.decidida_por) == ("aprovada", "Filipe")


def test_aprovar_tecnologia_grava_ancora_de_projeto_com_a_url(pasta):
    _aprovar(pasta, _id(pasta, "projeto_novo"))

    _aprovar(pasta, _id(pasta, "tecnologia_nova", "Java"))

    inventario = _inventario(pasta)
    validar_conteudo(_blocos(pasta), inventario)
    item = next(i for i in inventario.techs if i.tech == "Java")
    assert [(a.tipo, a.ref, a.fonte) for a in item.ancoras] == [
        ("projeto", ID_PROJETO, f"{REPO_URL}/ficticio-api")
    ]


def test_aprovar_tecnologia_ja_existente_acrescenta_a_ancora_sem_duplicar_a_tech(pasta):
    _aprovar(pasta, _id(pasta, "projeto_novo"))
    blocos = yaml.safe_load((pasta / PASTA / "blocos.yaml").read_text(encoding="utf-8"))
    blocos["blocos"].append({"id": "exp_x", "tipo": "experiencia"})
    (pasta / PASTA / "blocos.yaml").write_text(yaml.safe_dump(blocos), encoding="utf-8")
    ancora = {"tipo": "experiencia", "ref": "exp_x", "fonte": "guia"}
    (pasta / PASTA / "inventario.yaml").write_text(
        yaml.safe_dump({"techs": [{"tech": "java", "ancoras": [ancora]}]}), encoding="utf-8"
    )

    _aprovar(pasta, _id(pasta, "tecnologia_nova", "Java"))

    techs = _inventario(pasta).techs
    assert [t.tech for t in techs] == ["java"]
    assert [a.fonte for a in techs[0].ancoras] == ["guia", f"{REPO_URL}/ficticio-api"]


def test_aprovar_tecnologia_antes_do_projeto_e_recusado_sem_gravar(pasta):
    with pytest.raises(ProjetoNaoAprovado):
        _aprovar(pasta, _id(pasta, "tecnologia_nova", "Java"))

    assert not (pasta / PASTA / "inventario.yaml").exists()
    assert not (pasta / PASTA / "blocos.yaml").exists()


def test_aprovar_preserva_os_blocos_que_ja_existiam(pasta):
    existente = {"id": "exp_x", "tipo": "experiencia", "imutavel": {}}
    (pasta / PASTA / "blocos.yaml").write_text(
        yaml.safe_dump({"idiomas": ["pt", "en"], "blocos": [existente]}), encoding="utf-8"
    )

    _aprovar(pasta, _id(pasta, "projeto_novo"))

    assert [b.id for b in _blocos(pasta).blocos] == ["exp_x", ID_PROJETO]


def test_aprovar_duas_vezes_e_recusado(pasta):
    sugestao_id = _id(pasta, "projeto_novo")
    _aprovar(pasta, sugestao_id)

    with pytest.raises(JaDecidida):
        _aprovar(pasta, sugestao_id)


def test_aprovar_sem_nome_de_quem_aprova_e_recusado(pasta):
    with pytest.raises(ValueError, match="quem"):
        _aprovar(pasta, _id(pasta, "projeto_novo"), por="  ")

    assert not (pasta / PASTA / "blocos.yaml").exists()


def test_aprovar_id_inexistente_e_recusado(pasta):
    with pytest.raises(SugestaoInexistente):
        _aprovar(pasta, "sug_nao_existe")


def test_aprovar_tecnologia_com_bloco_de_outro_tipo_nao_grava(pasta):
    _aprovar(pasta, _id(pasta, "projeto_novo"))
    texto = (pasta / PASTA / "blocos.yaml").read_text(encoding="utf-8")
    (pasta / PASTA / "blocos.yaml").write_text(
        texto.replace("tipo: projeto", "tipo: experiencia"), encoding="utf-8"
    )

    with pytest.raises(ValueError):
        _aprovar(pasta, _id(pasta, "tecnologia_nova", "Java"))

    assert not (pasta / PASTA / "inventario.yaml").exists()


def test_rejeitar_exige_motivo_e_nao_toca_os_blocos(pasta):
    sugestao_id = _id(pasta, "projeto_novo")

    with pytest.raises(ValueError, match="motivo"):
        rejeitar(
            sugestao_id,
            "Filipe",
            " ",
            DEPOIS,
            pasta,
            configuracao_conteudo(),
            configuracao_sincronizacao(),
        )
    decidida = rejeitar(
        sugestao_id,
        "Filipe",
        "projeto de disciplina",
        DEPOIS,
        pasta,
        configuracao_conteudo(),
        configuracao_sincronizacao(),
    )

    assert (decidida.status, decidida.motivo) == ("rejeitada", "projeto de disciplina")
    assert not (pasta / PASTA / "blocos.yaml").exists()


def test_comando_lista_e_aprova_pelo_id(pasta, capsys):
    sugestao_id = _id(pasta, "projeto_novo")

    assert executar(["--listar"], pasta, AGORA) == 0
    assert sugestao_id in capsys.readouterr().out
    assert executar(["--id", sugestao_id, "--por", "Filipe"], pasta, DEPOIS) == 0
    assert _blocos(pasta).blocos[0].id == ID_PROJETO


def test_comando_sem_quem_aprova_falha_sem_gravar(pasta, capsys):
    assert executar(["--id", _id(pasta, "projeto_novo")], pasta, DEPOIS) == 2
    assert not (pasta / PASTA / "blocos.yaml").exists()


def test_comando_rejeita_com_motivo(pasta):
    sugestao_id = _id(pasta, "projeto_novo")

    assert executar(["--id", sugestao_id, "--por", "F", "--rejeitar"], pasta, DEPOIS) == 2
    assert (
        executar(
            ["--id", sugestao_id, "--por", "F", "--rejeitar", "--motivo", "nao e meu"],
            pasta,
            DEPOIS,
        )
        == 0
    )


def test_falha_ao_gravar_as_sugestoes_depois_do_bloco_pode_ser_reaprovada(pasta, monkeypatch):
    sugestao_id = _id(pasta, "projeto_novo")
    original = aprovar_modulo.gravar_sugestoes

    def falha(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(aprovar_modulo, "gravar_sugestoes", falha)
    with pytest.raises(OSError):
        _aprovar(pasta, sugestao_id)
    monkeypatch.setattr(aprovar_modulo, "gravar_sugestoes", original)

    decidida = _aprovar(pasta, sugestao_id)

    assert decidida.status == "aprovada"
    assert [b.id for b in _blocos(pasta).blocos] == [ID_PROJETO]


def test_reaprovar_nao_aceita_bloco_de_mesmo_id_apontando_para_outro_lugar(pasta):
    sugestao_id = _id(pasta, "projeto_novo")
    outro = {
        "id": ID_PROJETO,
        "tipo": "projeto",
        "imutavel": {"link": {"pt": "https://github.com/alguem-outro/ficticio-api"}},
    }
    (pasta / PASTA / "blocos.yaml").write_text(
        yaml.safe_dump({"idiomas": ["pt"], "blocos": [outro]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="ja existe"):
        _aprovar(pasta, sugestao_id)
