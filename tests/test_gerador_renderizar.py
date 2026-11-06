from __future__ import annotations

import re

import pytest
import yaml
from apoio_gerador import (
    ATAQUES,
    COMANDOS_DE_ESCAPE,
    CONTROLES,
    conteudo_ficticio,
    slots_ficticios,
    travado_ficticio,
)
from jinja2.exceptions import SecurityError

from src.conteudo.arquivo import gravar
from src.conteudo.configuracao import configuracao_conteudo
from src.gerador.configuracao import configuracao_gerador
from src.gerador.erros import (
    IdiomaNaoSuportado,
    SlotAusente,
    SlotInvalido,
    SlotNaoDeclarado,
    TechForaDoInventario,
    TemplateInvalido,
    TravadoInvalido,
)
from src.gerador.escape import LatexSeguro
from src.gerador.renderizar import criar_ambiente, renderizar, variaveis_do_template
from src.gerador.travado import carregar_travado

COMANDO = re.compile(r"\\([A-Za-z]+)")
FIM_DO_CABECALHO = r"\section{"
PRIMITIVAS_PERIGOSAS = [
    "\\input",
    "\\include",
    "\\write",
    "\\immediate",
    "\\openin",
    "\\catcode",
    "\\def",
    "\\newcommand",
    "\\csname",
    "\\usepackage",
]
SLOTS_DE_TEXTO = ["sobre", "disciplinas", "bullet_experiencia", "bullet_projeto"]


@pytest.fixture(scope="module")
def config():
    return configuracao_gerador()


@pytest.fixture(scope="module")
def conteudo():
    return conteudo_ficticio()


def _gerar(conteudo, config, idioma="pt", slots=None, travado=None):
    blocos, inventario = conteudo
    slots = slots if slots is not None else slots_ficticios(blocos, idioma)
    return renderizar(idioma, slots, travado or travado_ficticio(), blocos, inventario, config)


def _com_texto(slots: dict, onde: str, texto: str) -> dict:
    novos = {
        "sobre": dict(slots["sobre"]),
        "disciplinas": list(slots["disciplinas"]),
        "experiencias": [dict(e) for e in slots["experiencias"]],
        "projetos": [dict(e) for e in slots["projetos"]],
    }
    if onde == "sobre":
        novos["sobre"] = {"texto": texto, "techs": []}
    elif onde == "disciplinas":
        novos["disciplinas"][0] = texto
    elif onde == "bullet_experiencia":
        novos["experiencias"][0]["bullets"] = [{"texto": texto, "techs": []}]
    else:
        novos["projetos"][0]["bullets"] = [{"texto": texto, "techs": []}]
    return novos


def _comandos(texto: str) -> set[str]:
    return set(COMANDO.findall(texto))


def test_renderiza_pt_com_cabecalho_do_travado_e_techs_do_inventario(conteudo, config):
    tex = _gerar(conteudo, config, "pt")

    assert r"\usepackage[brazil]{babel}" in tex
    assert "PESSOA FICTICIA" in tex
    assert r"\href{mailto:pessoa@exemplo.invalid}{pessoa@exemplo.invalid}" in tex
    assert "Cidade Exemplo" in tex
    assert r"\section{Sobre}" in tex
    assert r"\tech{Python}" in tex
    assert r"Visão \& Borda" in tex
    assert r"\href{https://example.invalid/alfa}{example.invalid/alfa}" in tex
    assert r"\tech{face\_recognition}" in tex
    assert tex.rstrip().endswith(r"\end{document}")


def test_renderiza_en_com_babel_e_secoes_em_ingles(conteudo, config):
    tex = _gerar(conteudo, config, "en")

    assert r"\usepackage[english]{babel}" in tex
    assert "Example City" in tex
    assert r"\section{About}" in tex
    assert r"\section{Experience}" in tex
    assert "Built an API" in tex


def test_idioma_sem_template_ou_sem_blocos_e_recusado(conteudo, config):
    with pytest.raises(IdiomaNaoSuportado):
        _gerar(conteudo, config, "fr", slots={})


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_templates_nao_trazem_dado_pessoal_nem_link(config, idioma):
    from src.config import RAIZ

    arquivo = RAIZ / config.templates.pasta / config.templates.arquivos[idioma]
    fonte = arquivo.read_text(encoding="utf-8")

    assert "@" not in fonte
    assert "https://" not in fonte
    assert "mailto:" not in fonte


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_template_usa_todos_os_slots_declarados_e_nada_alem(config, idioma):
    variaveis = variaveis_do_template(config, idioma)

    assert variaveis == set(config.slots) | set(config.travado.nomes)


@pytest.mark.parametrize("idioma", ["pt", "en"])
@pytest.mark.parametrize("onde", SLOTS_DE_TEXTO)
def test_preambulo_e_cabecalho_nao_mudam_com_o_conteudo_dos_slots(conteudo, config, idioma, onde):
    blocos, _ = conteudo
    base = _gerar(conteudo, config, idioma)
    outro = _gerar(
        conteudo,
        config,
        idioma,
        slots=_com_texto(slots_ficticios(blocos, idioma), onde, r"\input{/etc/passwd} ^^5c"),
    )

    assert base[: base.index(FIM_DO_CABECALHO)] == outro[: outro.index(FIM_DO_CABECALHO)]


@pytest.mark.parametrize("onde", SLOTS_DE_TEXTO)
@pytest.mark.parametrize("ataque", ATAQUES)
def test_ataque_latex_em_qualquer_slot_vira_texto_inerte(conteudo, config, onde, ataque):
    blocos, _ = conteudo
    base = slots_ficticios(blocos, "pt")
    limpo = _gerar(conteudo, config, "pt", slots=_com_texto(base, onde, "texto simples"))

    atacado = _gerar(conteudo, config, "pt", slots=_com_texto(base, onde, f"antes {ataque} depois"))

    assert _comandos(atacado) - _comandos(limpo) <= COMANDOS_DE_ESCAPE
    assert "^^" not in atacado
    for primitiva in PRIMITIVAS_PERIGOSAS:
        assert atacado.count(primitiva) == limpo.count(primitiva)
    assert atacado.count(r"\begin{document}") == 1
    assert atacado.count(r"\end{document}") == 1
    assert atacado.count(r"\begin{itemize}") == atacado.count(r"\end{itemize}")


@pytest.mark.parametrize("onde", SLOTS_DE_TEXTO)
@pytest.mark.parametrize("controle", CONTROLES)
def test_controle_em_qualquer_slot_e_recusado(conteudo, config, onde, controle):
    blocos, _ = conteudo
    slots = _com_texto(slots_ficticios(blocos, "pt"), onde, controle)

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


@pytest.mark.parametrize("campo", ["nome", "telefone"])
@pytest.mark.parametrize("ataque", ATAQUES)
def test_ataque_nos_dados_travados_vira_texto_inerte(conteudo, config, campo, ataque):
    limpo = _gerar(conteudo, config, "pt")
    travado = travado_ficticio().model_copy(
        update={
            "cabecalho": travado_ficticio().cabecalho.model_copy(update={campo: f"x {ataque} y"})
        }
    )

    atacado = _gerar(conteudo, config, "pt", travado=travado)

    assert _comandos(atacado) - _comandos(limpo) <= COMANDOS_DE_ESCAPE
    assert "^^" not in atacado


@pytest.mark.parametrize("ataque", ATAQUES)
def test_ataque_na_localizacao_e_na_formacao_vira_texto_inerte(conteudo, config, ataque):
    limpo = _gerar(conteudo, config, "pt")
    base = travado_ficticio()
    travado = base.model_copy(
        update={
            "cabecalho": base.cabecalho.model_copy(
                update={"localizacao": {"pt": ataque, "en": "x"}}
            ),
            "formacao": base.formacao.model_copy(
                update={"instituicao": {"pt": ataque, "en": "x"}, "periodo": ataque}
            ),
        }
    )

    atacado = _gerar(conteudo, config, "pt", travado=travado)

    assert _comandos(atacado) - _comandos(limpo) <= COMANDOS_DE_ESCAPE


@pytest.mark.parametrize(
    "email",
    ["a@b.invalid}\\input{x", "a b@c.invalid", "a@b", "\\write18@x.invalid", "a@b.invalid\u202e"],
)
def test_email_malicioso_no_travado_e_recusado(conteudo, config, email):
    base = travado_ficticio()
    travado = base.model_copy(
        update={"cabecalho": base.cabecalho.model_copy(update={"email": email})}
    )

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", travado=travado)


def test_travado_sem_localizacao_no_idioma_e_recusado(conteudo, config):
    base = travado_ficticio()
    travado = base.model_copy(
        update={"cabecalho": base.cabecalho.model_copy(update={"localizacao": {"pt": "x"}})}
    )

    with pytest.raises(TravadoInvalido):
        _gerar(conteudo, config, "en", travado=travado)


@pytest.mark.parametrize("ataque", ATAQUES)
def test_fato_imutavel_do_bloco_tambem_e_escapado(conteudo, config, ataque):
    blocos, inventario = conteudo
    limpo = _gerar(conteudo, config, "pt")
    trocados = []
    for bloco in blocos.blocos:
        if bloco.id == "exp_empresa_exemplo_ltda":
            imutavel = {campo: dict(valores) for campo, valores in bloco.imutavel.items()}
            imutavel["cargo"]["pt"] = ataque
            bloco = bloco.model_copy(update={"imutavel": imutavel})
        trocados.append(bloco)
    hostil = blocos.model_copy(update={"blocos": trocados})

    atacado = renderizar(
        "pt",
        slots_ficticios(blocos, "pt"),
        travado_ficticio(),
        hostil,
        inventario,
        config,
    )

    assert _comandos(atacado) - _comandos(limpo) <= COMANDOS_DE_ESCAPE


def test_slot_nao_declarado_e_recusado(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt") | {"preambulo": r"\usepackage{shellesc}"}

    with pytest.raises(SlotNaoDeclarado):
        _gerar(conteudo, config, "pt", slots=slots)


def test_slot_declarado_ausente_e_recusado(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt")
    del slots["projetos"]

    with pytest.raises(SlotAusente):
        _gerar(conteudo, config, "pt", slots=slots)


def test_nome_de_slot_do_travado_nao_e_slot_preenchivel(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt") | {"cabecalho": {"nome": "outro"}}

    with pytest.raises(SlotNaoDeclarado):
        _gerar(conteudo, config, "pt", slots=slots)


def test_slot_acima_do_limite_do_config_e_recusado(conteudo, config):
    blocos, _ = conteudo
    base = slots_ficticios(blocos, "pt")
    limite = config.slots["sobre"].max_chars

    assert _gerar(conteudo, config, "pt", slots=_com_texto(base, "sobre", "a" * limite))
    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=_com_texto(base, "sobre", "a" * (limite + 1)))


def test_lista_acima_do_limite_de_itens_e_recusada(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt")
    slots["disciplinas"] = ["x"] * (config.slots["disciplinas"].max_itens + 1)

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


def test_bullets_acima_do_limite_sao_recusados(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt")
    bullet = {"texto": "ok", "techs": []}
    slots["experiencias"][0]["bullets"] = [bullet] * (config.slots["experiencias"].max_bullets + 1)

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


def test_bloco_desconhecido_ou_de_tipo_errado_e_recusado(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt")
    slots["experiencias"][0]["bloco"] = "exp_inexistente"
    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)

    slots = slots_ficticios(blocos, "pt")
    slots["experiencias"][0]["bloco"] = "proj_projeto_alfa_beta"
    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


def test_bloco_repetido_e_recusado(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt")
    slots["experiencias"][1]["bloco"] = slots["experiencias"][0]["bloco"]

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


@pytest.mark.parametrize("campo", ["cargo", "empresa", "periodo", "imutavel", "latex"])
def test_llm_nao_sobrescreve_fato_imutavel_nem_acrescenta_campo(conteudo, config, campo):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt")
    slots["experiencias"][0][campo] = "inventado"

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


def test_campo_extra_no_bullet_e_recusado(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt")
    slots["experiencias"][0]["bullets"][0]["latex"] = r"\input{x}"

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


@pytest.mark.parametrize("valor", ["texto cru", 7, None, ["a"], {"texto": 5, "techs": []}])
def test_formato_errado_do_slot_de_texto_e_recusado(conteudo, config, valor):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt") | {"sobre": valor}

    with pytest.raises(SlotInvalido):
        _gerar(conteudo, config, "pt", slots=slots)


def test_tech_fora_do_inventario_e_recusada_no_slot(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt") | {
        "sobre": {"texto": "Domino Kubernetes", "techs": ["Kubernetes"]}
    }

    with pytest.raises(TechForaDoInventario):
        _gerar(conteudo, config, "pt", slots=slots)


def test_valor_do_slot_nunca_e_interpretado_como_template(conteudo, config):
    blocos, _ = conteudo
    slots = slots_ficticios(blocos, "pt") | {
        "sobre": {"texto": "<< 7*7 >> <% for x in y %>", "techs": []}
    }

    tex = _gerar(conteudo, config, "pt", slots=slots)

    assert r"\textless{}\textless{} 7*7 \textgreater{}\textgreater{}" in tex
    assert r"\textless{}\% for x in y \%\textgreater{}" in tex
    assert "49" not in tex


def test_slot_fora_do_template_nao_renderiza(conteudo, config, tmp_path):
    blocos, _ = conteudo
    fonte = (
        r"\begin{document}<< cabecalho.nome >> << disciplinas >> "
        r"<< experiencias|length >> << projetos|length >> \end{document}"
    )
    (tmp_path / "cv_pt.tex.j2").write_text(fonte, encoding="utf-8")
    sem_sobre = config.model_copy(
        update={
            "templates": config.templates.model_copy(
                update={"pasta": str(tmp_path), "arquivos": {"pt": "cv_pt.tex.j2"}}
            )
        }
    )
    slots = slots_ficticios(blocos, "pt") | {
        "sobre": {"texto": "SOBRE_QUE_NAO_APARECE", "techs": []}
    }

    tex = _gerar(conteudo, sem_sobre, "pt", slots=slots)

    assert "SOBRE_QUE_NAO_APARECE" not in tex
    assert "Estudante" not in tex


def test_variavel_nao_declarada_no_template_e_recusada(conteudo, config, tmp_path):
    (tmp_path / "cv_pt.tex.j2").write_text("<< segredo >> << sobre >>", encoding="utf-8")
    hostil = config.model_copy(
        update={
            "templates": config.templates.model_copy(
                update={"pasta": str(tmp_path), "arquivos": {"pt": "cv_pt.tex.j2"}}
            )
        }
    )

    with pytest.raises(TemplateInvalido):
        _gerar(conteudo, hostil, "pt")


def test_sandbox_recusa_atributo_arbitrario(config):
    ambiente = criar_ambiente(config, ".")

    for fonte in (
        "<< sobre.__class__ >>",
        "<< sobre.__class__.__mro__ >>",
        "<< ''.__class__.__base__.__subclasses__() >>",
        "<< '{0.__class__}'.format(sobre) >>",
        "<< cycler.__init__.__globals__ >>",
    ):
        with pytest.raises(SecurityError):
            ambiente.from_string(fonte).render(sobre="x", cycler=object())


def test_variavel_fora_do_contexto_nao_existe(config):
    ambiente = criar_ambiente(config, ".")

    with pytest.raises(Exception, match="undefined"):
        ambiente.from_string("<< ausente >>").render()


def test_toda_saida_de_variavel_e_escapada_por_padrao(config):
    ambiente = criar_ambiente(config, ".")

    assert ambiente.from_string("<< valor >>").render(valor="a_b & c") == r"a\_b \& c"
    assert ambiente.from_string("<< valor|upper >>").render(valor="a_b") == r"A\_B"
    assert ambiente.from_string("<< valor >>").render(valor=12) == "12"
    assert ambiente.from_string("<< valor >>").render(valor=LatexSeguro(r"\tech{x}")) == r"\tech{x}"


def test_delimitadores_do_jinja_nao_colidem_com_latex(config):
    ambiente = criar_ambiente(config, ".")
    latex = r"\begin{itemize}\item {\bf x} {{ 7*7 }} {% if x %} \% # {# c #}"

    assert ambiente.from_string(latex).render() == latex


def test_laco_do_template_usa_delimitador_proprio(config):
    ambiente = criar_ambiente(config, ".")

    saida = ambiente.from_string("<% for x in itens %>[<< x >>]<% endfor %>").render(
        itens=["a_", "b"]
    )

    assert saida == r"[a\_][b]"


def test_carregar_travado_le_de_dados_e_recusa_campo_extra(tmp_path):
    config_conteudo = configuracao_conteudo()
    config = configuracao_gerador()
    blocos, inventario = conteudo_ficticio()
    gravar(blocos, inventario, tmp_path, config_conteudo)
    destino = tmp_path / config_conteudo.subpasta / config.travado.arquivo
    bruto = {
        "cabecalho": {
            "nome": "Pessoa Ficticia",
            "email": "pessoa@exemplo.invalid",
            "localizacao": {"pt": "Cidade", "en": "City"},
        },
        "formacao": {"instituicao": {"pt": "U", "en": "U"}, "periodo": "2020 -- 2024"},
    }
    destino.write_text(yaml.safe_dump(bruto), encoding="utf-8")

    travado = carregar_travado(tmp_path, config_conteudo, config)

    assert travado.cabecalho.nome == "Pessoa Ficticia"
    assert travado.cabecalho.telefone is None

    bruto["cabecalho"]["preambulo"] = r"\usepackage{x}"
    destino.write_text(yaml.safe_dump(bruto), encoding="utf-8")
    with pytest.raises(TravadoInvalido):
        carregar_travado(tmp_path, config_conteudo, config)


def test_carregar_travado_sem_arquivo_explica(tmp_path):
    with pytest.raises(TravadoInvalido):
        carregar_travado(tmp_path, configuracao_conteudo(), configuracao_gerador())
