from __future__ import annotations

import pytest
from apoio_validador import configuracao_com, contexto_rico, inventario_rico, tex_rico

from src.validador.conteudo import validar_conteudo
from src.validador.resultado import Regra


def achados(tex, idioma="pt", config=None):
    return validar_conteudo(tex, inventario_rico(), contexto_rico(idioma), config)


def regras(tex, idioma="pt", config=None):
    return {v.regra for v in achados(tex, idioma, config)}


def so(tex, regra, idioma="pt", config=None):
    return [v for v in achados(tex, idioma, config) if v.regra == regra]


def test_preambulo_alterado_e_recusado_por_v6():
    tex = tex_rico().replace("\\pagestyle{empty}", "\\pagestyle{plain}")

    achado = so(tex, Regra.PREAMBULO)

    assert [v.codigo for v in achado] == ["V6"]
    assert "pagestyle{plain}" in achado[0].trecho
    assert achado[0].sugestao


def test_preambulo_com_linha_a_menos_e_recusado_por_v6():
    tex = tex_rico().replace("\\usepackage{enumitem}\n", "")

    assert so(tex, Regra.PREAMBULO)


@pytest.mark.parametrize(
    "mudanca",
    [
        ("margin=1.5cm", "margin=1.1cm"),
        ("\\setlength{\\parindent}{0pt}", "\\setlength{\\parindent}{0pt}\n\\linespread{0.95}"),
    ],
)
def test_parametros_da_ordem_de_corte_nao_sao_recusados_por_v6(mudanca):
    tex = tex_rico().replace(*mudanca)

    assert tex != tex_rico()
    assert not so(tex, Regra.PREAMBULO)


def test_preambulo_de_outro_idioma_e_recusado_por_v6():
    assert so(tex_rico("en"), Regra.PREAMBULO, idioma="pt")


@pytest.mark.parametrize(
    "troca",
    [
        ("pessoa@exemplo.invalid", "outra@exemplo.invalid"),
        ("PESSOA FICTICIA", "OUTRA PESSOA"),
        ("(00) 00000-0000", "(11) 99999-9999"),
        ("Cidade Exemplo", "Outra Cidade"),
        ("Universidade Exemplo", "Universidade Falsa"),
        ("2020 -- 2024", "2018 -- 2024"),
    ],
)
def test_cabecalho_ou_formacao_diferente_do_base_e_recusado_por_v7(troca):
    tex = tex_rico().replace(*troca)

    achado = so(tex, Regra.CABECALHO)

    assert achado
    assert achado[0].codigo == "V7"


def test_link_extra_no_cabecalho_e_recusado_por_v7():
    tex = tex_rico().replace(
        "(00) 00000-0000 \\\\", "(00) 00000-0000 \\href{https://example.invalid/x}{x} \\\\"
    )

    assert so(tex, Regra.CABECALHO)


def test_cabecalho_do_template_passa_em_v7_nos_dois_idiomas():
    assert not so(tex_rico("pt"), Regra.CABECALHO, "pt")
    assert not so(tex_rico("en"), Regra.CABECALHO, "en")


@pytest.mark.parametrize(
    "troca",
    [
        ("Desenvolvedora Estagiária", "Desenvolvedora Sênior"),
        ("Empresa Exemplo Ltda, Divisão Dados", "Outra Empresa"),
        ("2023 -- Presente", "2021 -- Presente"),
    ],
)
def test_experiencia_com_cargo_empresa_ou_periodo_trocado_e_recusada_por_v8(troca):
    tex = tex_rico().replace(*troca)

    achado = so(tex, Regra.EXPERIENCIAS)

    assert achado
    assert achado[0].codigo == "V8"
    assert achado[0].trecho


def test_experiencias_fora_da_ordem_dos_blocos_sao_recusadas_por_v8():
    tex = tex_rico()
    inicio = tex.index("\\textbf{Desenvolvedora")
    meio = tex.index("\\textbf{Pesquisadora")
    fim = tex.index("\\section{Projetos}")
    invertido = tex[:inicio] + tex[meio:fim] + tex[inicio:meio] + tex[fim:]

    assert so(invertido, Regra.EXPERIENCIAS)


def test_experiencia_removida_e_recusada_por_v8():
    tex = tex_rico()
    meio = tex.index("\\textbf{Pesquisadora")
    fim = tex.index("\\section{Projetos}")

    assert so(tex[:meio] + tex[fim:], Regra.EXPERIENCIAS)


def test_experiencia_inventada_e_recusada_por_v8():
    extra = (
        "\\textbf{Gerente, Empresa Falsa} \\hfill 2020 -- 2021\n"
        "\\begin{itemize}\n    \\item Fiz algo.\n\\end{itemize}\n"
    )
    tex = tex_rico().replace("\\section{Projetos}", extra + "\\section{Projetos}")

    assert so(tex, Regra.EXPERIENCIAS)


def test_experiencias_do_template_passam_em_v8_nos_dois_idiomas():
    assert not so(tex_rico("pt"), Regra.EXPERIENCIAS, "pt")
    assert not so(tex_rico("en"), Regra.EXPERIENCIAS, "en")


def test_experiencia_sem_bullet_e_recusada_por_v9():
    tex = tex_rico()
    inicio = tex.index("\\textbf{Pesquisadora")
    abre = tex.index("\\begin{itemize}", inicio)
    fecha = tex.index("\\end{itemize}", abre) + len("\\end{itemize}")

    achado = so(tex[:abre] + tex[fecha:], Regra.EXPERIENCIA_VAZIA)

    assert [v.codigo for v in achado] == ["V9"]
    assert "Pesquisadora" in achado[0].trecho


def test_experiencia_com_lista_vazia_e_recusada_por_v9():
    tex = tex_rico().replace(
        "    \\item Reconhecimento com \\tech{face\\_recognition} em hardware de borda.\n", ""
    )

    assert so(tex, Regra.EXPERIENCIA_VAZIA)


def test_experiencias_com_bullet_passam_em_v9():
    assert not so(tex_rico(), Regra.EXPERIENCIA_VAZIA)


def test_dois_projetos_sao_recusados_por_v15():
    tex = tex_rico()
    corte = tex.index("\\textbf{Projeto Delta}")

    achado = so(tex[:corte] + "\\end{document}\n", Regra.PROJETOS)

    assert [v.codigo for v in achado] == ["V15"]


def test_cinco_projetos_sao_recusados_por_v15():
    extra = "\\textbf{Projeto Extra} \\hfill \\href{https://example.invalid/e}{example.invalid/e}\n"
    tex = tex_rico().replace("\\end{document}", extra * 2 + "\\end{document}")

    assert so(tex, Regra.PROJETOS)


def test_mais_projetos_antes_de_outro_projeto_e_recusado_por_v15():
    mais = "\\textbf{Mais projetos} \\hfill \\href{https://example.invalid}{example.invalid}\n"
    tex = tex_rico().replace("\\textbf{Projeto Delta}", mais + "\\textbf{Projeto Delta}")

    achado = so(tex, Regra.PROJETOS)

    assert achado
    assert "Mais projetos" in achado[0].trecho


def test_mais_projetos_por_ultimo_nao_conta_como_projeto_e_passa_em_v15():
    mais = "\\textbf{Mais projetos} \\hfill \\href{https://example.invalid}{example.invalid}\n"
    tex = tex_rico().replace("\\end{document}", mais + "\\end{document}")

    assert not so(tex, Regra.PROJETOS)


def test_mais_projetos_em_ingles_segue_o_rotulo_do_idioma():
    mais = "\\textbf{More projects} \\hfill \\href{https://example.invalid}{example.invalid}\n"
    tex = tex_rico("en").replace("\\textbf{Projeto Delta}", mais + "\\textbf{Projeto Delta}")

    assert so(tex, Regra.PROJETOS, idioma="en")


def test_limites_de_projetos_vem_da_configuracao():
    config = configuracao_com(conteudo__projetos__minimo=1, conteudo__projetos__maximo=1)

    assert so(tex_rico(), Regra.PROJETOS, config=config)


def test_secao_de_skills_e_recusada_por_v14():
    tex = tex_rico().replace(
        "\\section{Projetos}", "\\section{Skills}\nPython\n\\section{Projetos}"
    )

    achado = so(tex, Regra.ESTRUTURA)

    assert achado
    assert achado[0].codigo == "V14"
    assert "Skills" in achado[0].trecho


def test_secao_nova_e_recusada_por_v14():
    tex = tex_rico().replace(
        "\\section{Projetos}", "\\section{Hobbies}\nxadrez\n\\section{Projetos}"
    )

    assert so(tex, Regra.ESTRUTURA)


def test_secao_fora_de_ordem_e_recusada_por_v14():
    tex = tex_rico()
    inicio = tex.index("\\section{Formação}")
    meio = tex.index("\\section{Experiência}")
    fim = tex.index("\\section{Projetos}")
    trocado = tex[:inicio] + tex[meio:fim] + tex[inicio:meio] + tex[fim:]

    assert so(trocado, Regra.ESTRUTURA)


def test_secao_ausente_e_recusada_por_v14():
    tex = tex_rico()
    inicio = tex.index("\\section{Formação}")
    fim = tex.index("\\section{Experiência}")

    assert so(tex[:inicio] + tex[fim:], Regra.ESTRUTURA)


def test_negrito_fora_de_tech_no_bullet_e_recusado_por_v14():
    tex = tex_rico().replace("Mantive filas com", "Mantive \\textbf{filas} com")

    achado = so(tex, Regra.ESTRUTURA)

    assert achado
    assert "textbf" in achado[0].trecho


def test_negrito_fora_de_tech_no_sobre_e_recusado_por_v14():
    tex = tex_rico().replace("Estudante de exemplo", "\\bfseries Estudante de exemplo")

    assert so(tex, Regra.ESTRUTURA)


def test_negrito_dentro_de_tech_e_nos_titulos_passa_em_v14():
    assert not so(tex_rico(), Regra.ESTRUTURA)
    assert not so(tex_rico("en"), Regra.ESTRUTURA, "en")


def test_titulo_de_secao_em_ingles_na_versao_pt_e_recusado_por_v14():
    tex = tex_rico().replace("\\section{Sobre}", "\\section{About}")

    assert so(tex, Regra.ESTRUTURA)


def test_underline_cru_na_url_exibida_e_recusado_por_v16():
    tex = tex_rico().replace("example.invalid/gama}", "example.invalid/meu_projeto}")

    achado = so(tex, Regra.ESCAPE)

    assert [v.codigo for v in achado] == ["V16"]
    assert "meu_projeto" in achado[0].trecho


def test_e_comercial_cru_no_titulo_e_recusado_por_v16():
    tex = tex_rico().replace("Visão \\& Borda", "Visão & Borda")

    assert so(tex, Regra.ESCAPE)


def test_tech_com_underline_cru_e_recusado_por_v16():
    tex = tex_rico().replace("face\\_recognition", "face_recognition")

    assert so(tex, Regra.ESCAPE)


def test_simbolos_escapados_e_destino_do_link_passam_em_v16():
    assert not so(tex_rico(), Regra.ESCAPE)
    tex = tex_rico().replace("https://example.invalid/gama", "https://example.invalid/a_b")

    assert not so(tex, Regra.ESCAPE)


def test_simbolos_a_conferir_vem_da_configuracao():
    config = configuracao_com(conteudo__escapes__simbolos=["@"])
    tex = tex_rico().replace("Mantive filas", "Mantive @ filas")

    assert so(tex, Regra.ESCAPE, config=config)


def test_babel_de_outro_idioma_e_recusado_por_v19():
    tex = tex_rico().replace("[brazil]{babel}", "[english]{babel}")

    achado = so(tex, Regra.IDIOMA)

    assert [v.codigo for v in achado] == ["V19"]


def test_texto_em_ingles_na_versao_pt_e_recusado_por_v19():
    tex = tex_rico().replace(
        "Mantive filas com \\tech{RabbitMQ}.",
        "Built the service with the API and the tests of the team \\tech{RabbitMQ}.",
    )

    achado = so(tex, Regra.IDIOMA)

    assert [v.codigo for v in achado] == ["V19"]
    assert "en" in achado[0].detalhe


def test_documento_no_idioma_certo_passa_em_v19():
    assert not so(tex_rico("pt"), Regra.IDIOMA, "pt")
    assert not so(tex_rico("en"), Regra.IDIOMA, "en")


def test_idioma_fora_dos_blocos_e_recusado():
    with pytest.raises(ValueError):
        validar_conteudo(tex_rico(), inventario_rico(), contexto_rico("fr"))
