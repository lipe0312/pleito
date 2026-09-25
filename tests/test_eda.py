from __future__ import annotations

from viabilidade.contratos import ModeloTrabalho, Senioridade, VagaBruta
from viabilidade.eda import perfilar, renderizar_markdown


def _vaga(**kw) -> VagaBruta:
    base = {
        "fonte": "greenhouse",
        "id_externo": "1",
        "url": "https://boards.greenhouse.io/x/1",
        "titulo": "Intern",
        "empresa": "X",
        "descricao": "d" * 400,
        "local": "Remote",
        "pais": "BR",
        "senioridade": Senioridade.ESTAGIO,
        "modelo": ModeloTrabalho.REMOTO,
    }
    base.update(kw)
    return VagaBruta(**base)


def test_perfil_vazio_nao_divide_por_zero():
    p = perfilar([])
    assert p.total == 0
    assert p.taxa_duplicidade == 0.0
    assert p.taxa_elegivel == 0.0


def test_duplicidade_detectada_entre_fontes():
    p = perfilar([_vaga(), _vaga(fonte="lever", id_externo="2", url="https://jobs.lever.co/x/2")])
    assert p.total == 2
    assert p.unicas == 1
    assert p.taxa_duplicidade == 0.5


def test_senior_nao_entra_em_elegiveis():
    p = perfilar([_vaga(), _vaga(id_externo="2", senioridade=Senioridade.SENIOR)])
    assert p.elegiveis == 1
    assert p.taxa_elegivel == 0.5


def test_campos_ausentes_sao_contados():
    p = perfilar([_vaga(id_externo="3", local="", descricao="curta")])
    assert p.campos_ausentes["local"] == 1
    assert p.campos_ausentes["descricao"] == 1


def test_markdown_inclui_todas_as_secoes():
    md = renderizar_markdown(perfilar([_vaga()]))
    for titulo in ("Por fonte", "Por senioridade", "Por modelo", "Por pais", "Campos ausentes"):
        assert titulo in md
