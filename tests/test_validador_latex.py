from __future__ import annotations

import pytest
from apoio_validador import configuracao_com, tex_com_corpo, tex_ficticio

from src.validador.configuracao import configuracao_validador
from src.validador.latex import validar_latex
from src.validador.resultado import Regra

ATAQUES_NO_CORPO = {
    "input": r"\input{/etc/passwd}",
    "include": r"\include{segredo}",
    "write18": r"\write18{touch /tmp/x}",
    "immediate_write18": r"\immediate\write18{touch /tmp/x}",
    "catcode": r"\catcode`\%=12",
    "def": r"\def\x{\input{/etc/passwd}}",
    "newcommand_no_corpo": r"\newcommand{\x}{y}",
    "renewcommand": r"\renewcommand{\tech}[1]{\input{#1}}",
    "csname": r"\csname input\endcsname{/etc/passwd}",
    "usepackage_no_corpo": r"\usepackage{shellesc}",
    "openin": r"\openin1=/etc/passwd",
    "openout": r"\openout1=/tmp/x",
    "read": r"\read1 to \x",
    "verb": r"\verb|x|",
    "expandafter": r"\expandafter\input\csname x\endcsname",
    "string": r"\string\input",
    "scantokens": r"\scantokens{x}",
    "espaco_depois_da_barra": "\\ input{/etc/passwd}",
    "quebra_depois_da_barra": "\\\ninput{/etc/passwd}",
    "tabulacao_depois_da_barra": "\\\tinput{/etc/passwd}",
    "codigo_hexadecimal": r"\in^^70ut{/etc/passwd}",
    "barra_em_hexadecimal": r"^^5cinput{/etc/passwd}",
    "ambiente_com_espaco": r"\begin {verbatim}x\end {verbatim}",
    "ambiente_com_quebra": "\\begin\n{verbatim}x\\end\n{verbatim}",
    "ambiente_com_comentario": "\\begin%\n{verbatim}x\\end{verbatim}",
    "ambiente_fora_da_lista": r"\begin{verbatim}x\end{verbatim}",
    "ambiente_lstlisting": r"\begin{lstlisting}x\end{lstlisting}",
    "href_run": r"\href{run:calc.exe}{abrir}",
    "href_javascript": r"\href{javascript:alert(1)}{abrir}",
    "href_file": r"\href{file:///etc/passwd}{abrir}",
    "href_com_quebra": "\\href\n{run:calc.exe}{abrir}",
    "simbolo_acento": r"\^e",
    "simbolo_aspas": r"\"a",
    "ponto_e_virgula_de_controle": r"\;",
    "textemdash": r"\textemdash{}",
}


def _regras(tex: str, config=None) -> list[Regra]:
    return [v.regra for v in validar_latex(tex, config or configuracao_validador())]


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_curriculo_gerado_pelo_template_passa(idioma):
    assert validar_latex(tex_ficticio(idioma), configuracao_validador()) == []


@pytest.mark.parametrize("ataque", ATAQUES_NO_CORPO.values(), ids=ATAQUES_NO_CORPO.keys())
def test_ataque_no_corpo_e_recusado(ataque):
    assert Regra.LATEX in _regras(tex_com_corpo(ataque))


@pytest.mark.parametrize("ataque", ["\\input{x}", "\\write18{x}", "\\def\\x{y}"])
def test_ataque_em_texto_logo_depois_de_comentario_e_recusado(ataque):
    assert Regra.LATEX in _regras(tex_com_corpo(f"% inocente\n{ataque}"))


def test_comando_dentro_de_comentario_nao_executa_e_nao_e_recusado():
    assert _regras(tex_com_corpo("% \\input{x}")) == []


def test_barra_escapada_seguida_de_texto_nao_vira_comando():
    assert _regras(tex_com_corpo("\\\\input e \\\\write")) == []


def test_preambulo_com_pacote_fora_da_lista_e_recusado():
    tex = tex_ficticio().replace("\\usepackage{xcolor}", "\\usepackage{shellesc}")

    assert Regra.LATEX in _regras(tex)


def test_preambulo_com_opcoes_de_pacote_permitido_passa():
    assert _regras(tex_ficticio()) == []


def test_preambulo_com_comando_fora_da_lista_e_recusado():
    tex = tex_ficticio().replace("\\pagestyle{empty}", "\\pagestyle{empty}\n\\input{x}")

    assert Regra.LATEX in _regras(tex)


def test_preambulo_so_pode_definir_comando_declarado():
    tex = tex_ficticio().replace(
        "\\pagestyle{empty}", "\\pagestyle{empty}\n\\newcommand{\\large}[1]{#1}"
    )

    assert Regra.LATEX in _regras(tex)


def test_classe_de_documento_fora_da_lista_e_recusada():
    tex = tex_ficticio().replace("{article}", "{minimal}")

    assert Regra.LATEX in _regras(tex)


def test_documento_sem_inicio_de_corpo_e_recusado():
    assert Regra.LATEX in _regras(tex_ficticio().replace("\\begin{document}", ""))


def test_documento_com_dois_inicios_de_corpo_e_recusado():
    tex = tex_com_corpo("\\begin{document}")

    assert Regra.LATEX in _regras(tex)


def test_comando_do_corpo_nao_vale_no_preambulo():
    tex = tex_ficticio().replace("\\pagestyle{empty}", "\\pagestyle{empty}\n\\hfill")

    assert Regra.LATEX in _regras(tex)


def test_allowlist_vem_da_configuracao():
    config = configuracao_com(latex__corpo__comandos=["tech", "begin", "end", "section", "href"])

    assert Regra.LATEX in _regras(tex_ficticio(), config)


def _com_preambulo(antigo: str, novo: str) -> str:
    tex = tex_ficticio()
    assert antigo in tex
    return tex.replace(antigo, novo)


OPCOES_MALICIOSAS = {
    "altura_de_pagina": ("\\usepackage{xcolor}", "\\usepackage[paperheight=9999cm]{geometry}"),
    "margem_negativa": (
        "[a4paper,margin=1.5cm]{geometry}",
        "[a4paper,margin=-90cm]{geometry}",
    ),
    "hyperref_autor": ("[hidelinks]{hyperref}", "[hidelinks,pdfauthor=x]{hyperref}"),
    "hyperref_so_autor": ("[hidelinks]{hyperref}", "[pdfauthor=x]{hyperref}"),
    "hyperref_com_chaves": ("[hidelinks]{hyperref}", "[pdftitle={a}]{hyperref}"),
    "opcao_em_pacote_sem_opcoes": ("\\usepackage{xcolor}", "\\usepackage[table]{xcolor}"),
    "opcao_vazia": ("[hidelinks]{hyperref}", "[hidelinks,]{hyperref}"),
    "classe_paisagem": ("[a4paper,10pt]{article}", "[a4paper,10pt,landscape]{article}"),
    "classe_duas_colunas": ("[a4paper,10pt]{article}", "[twocolumn]{article}"),
    "classe_corpo_enorme": ("[a4paper,10pt]{article}", "[a4paper,99pt]{article}"),
    "opcao_sem_fechar": ("[hidelinks]{hyperref}", "[hidelinks{hyperref}"),
}


@pytest.mark.parametrize("troca", OPCOES_MALICIOSAS.values(), ids=OPCOES_MALICIOSAS.keys())
def test_opcao_de_pacote_ou_classe_fora_da_allowlist_e_recusada(troca):
    antigo, novo = troca

    assert Regra.LATEX in _regras(_com_preambulo(antigo, novo))


def test_opcoes_do_template_nas_duas_linguas_passam():
    assert _regras(tex_ficticio("pt")) == []
    assert _regras(tex_ficticio("en")) == []


def test_opcoes_permitidas_vem_da_configuracao():
    tex = _com_preambulo("[hidelinks]{hyperref}", "[hidelinks,pdfauthor=x]{hyperref}")
    dados = configuracao_validador().model_dump()
    dados["latex"]["preambulo"]["pacotes"]["hyperref"] = ["hidelinks", "pdfauthor=x"]

    assert _regras(tex, configuracao_validador(dados)) == []


MEDIDAS_ABUSIVAS = {
    "vspace_negativo": "\\vspace{-9999pt}",
    "vspace_enorme": "\\vspace{9999pt}",
    "vspace_em_cm": "\\vspace{100cm}",
    "vspace_com_estica": "\\vspace{2mm plus 1fil}",
    "vspace_sem_chaves": "\\vspace 9pt",
    "vspace_unidade_fora_da_lista": "\\vspace{5em}",
    "vspace_sem_unidade": "\\vspace{9999}",
    "vspace_expressao": "\\vspace{\\dimexpr 9999pt}",
    "vspace_estrela": "\\vspace*{-9999pt}",
    "vspace_decimal": "\\vspace{-.5mm}",
}


@pytest.mark.parametrize("medida", MEDIDAS_ABUSIVAS.values(), ids=MEDIDAS_ABUSIVAS.keys())
def test_medida_fora_do_limite_no_corpo_e_recusada(medida):
    assert Regra.LATEX in _regras(tex_com_corpo(medida))


PREAMBULOS_ABUSIVOS = {
    "setlength_negativo": ("{\\parindent}{0pt}", "{\\parindent}{-9999pt}"),
    "setlength_enorme": ("{\\parindent}{0pt}", "{\\parindent}{9999pt}"),
    "titlespacing_enorme": ("{0pt}{2mm}{1mm}", "{0pt}{9999mm}{1mm}"),
    "titlespacing_negativo": ("{0pt}{2mm}{1mm}", "{0pt}{2mm}{-9999mm}"),
}


@pytest.mark.parametrize("troca", PREAMBULOS_ABUSIVOS.values(), ids=PREAMBULOS_ABUSIVOS.keys())
def test_medida_fora_do_limite_no_preambulo_e_recusada(troca):
    antigo, novo = troca

    assert Regra.LATEX in _regras(_com_preambulo(antigo, novo))


def test_medidas_do_template_passam():
    assert _regras(tex_com_corpo("\\vspace{2mm}\n\\vspace*{1mm}")) == []


def test_limite_de_medida_vem_da_configuracao():
    assert Regra.LATEX in _regras(tex_com_corpo("\\vspace{100cm}"))
    dados = configuracao_validador().model_dump()
    dados["latex"]["medidas"]["maximo_mm"] = 1000
    config = configuracao_validador(dados)

    assert _regras(tex_com_corpo("\\vspace{100cm}"), config) == []


def test_catcode_e_recusado_em_qualquer_forma():
    for ataque in ("\\catcode`\\%=12", "\\catcode 37=11", "\\catcode`\\\\=12 \\input{x}"):
        assert Regra.LATEX in _regras(tex_com_corpo(ataque))


def test_csname_e_recusado():
    assert Regra.LATEX in _regras(tex_com_corpo("\\csname write18\\endcsname{x}"))


def test_expandafter_e_recusado():
    assert Regra.LATEX in _regras(tex_com_corpo("\\expandafter\\def\\csname x\\endcsname{y}"))


def test_let_e_recusado():
    assert Regra.LATEX in _regras(tex_com_corpo("\\let\\x\\input \\x{y}"))


def test_til_ativo_nao_pode_ser_redefinido():
    for ataque in ("\\let~\\input", "\\def~{\\input{x}}", "\\catcode`\\~=0"):
        assert Regra.LATEX in _regras(tex_com_corpo(ataque))


def test_til_comum_no_texto_nao_e_recusado():
    assert _regras(tex_com_corpo("a~b")) == []


def test_barra_com_codigo_hexadecimal_e_recusada_pela_sequencia_proibida():
    violacoes = validar_latex(tex_com_corpo("^^5cinput{/etc/passwd}"), configuracao_validador())

    assert [v.regra for v in violacoes] == [Regra.LATEX]
    assert "^^" in violacoes[0].detalhe


def test_barra_seguida_de_codigo_hexadecimal_e_recusada():
    assert Regra.LATEX in _regras(tex_com_corpo("\\^^5cinput{x}"))


def test_sequencia_proibida_vem_da_configuracao():
    dados = configuracao_validador().model_dump()
    dados["latex"]["sequencias_proibidas"] = []

    assert _regras(tex_com_corpo("^^5cinput{x}"), configuracao_validador(dados)) == []


def test_newcommand_com_estrela_e_recusado_no_corpo():
    assert Regra.LATEX in _regras(tex_com_corpo("\\newcommand*{\\x}{\\input{y}}"))


def test_newcommand_com_estrela_e_recusado_no_preambulo_para_nome_nao_declarado():
    tex = _com_preambulo("\\pagestyle{empty}", "\\pagestyle{empty}\n\\newcommand*{\\large}[1]{#1}")

    assert Regra.LATEX in _regras(tex)


def test_newcommand_com_estrela_do_comando_declarado_passa():
    tex = _com_preambulo("\\newcommand{\\tech}", "\\newcommand*{\\tech}")

    assert _regras(tex) == []


COMANDOS_PARTIDOS_POR_COMENTARIO = {
    "nome_colado": "\\item%\nnomedocomando",
    "input_partido": "\\in%\nput{/etc/passwd}",
    "input_com_recuo": "\\in% x\n      put{/etc/passwd}",
    "write_partido": "\\wri%\n%\nte18{x}",
    "ambiente_partido": "\\begin{verb%\natim}",
}


@pytest.mark.parametrize(
    "ataque",
    COMANDOS_PARTIDOS_POR_COMENTARIO.values(),
    ids=COMANDOS_PARTIDOS_POR_COMENTARIO.keys(),
)
def test_comando_partido_por_comentario_e_lido_como_o_tex_le(ataque):
    assert Regra.LATEX in _regras(tex_com_corpo(ataque))


def test_comentario_nao_deixa_o_texto_seguinte_virar_parte_do_comando():
    assert _regras(tex_com_corpo("texto % nota\n   continua")) == []
    assert _regras(tex_com_corpo("\\hfill %\n  texto")) == []


DOMINIOS_FALSOS = {
    "dominio_estranho": "https://evil.example/x",
    "prefixo_colado": "https://evilgithub.com/x",
    "dominio_como_subdominio": "https://github.com.evil.com/x",
    "usuario_enganoso": "https://github.com@evil.com/x",
    "porta": "https://github.com:444/x",
    "usuario_em_dominio_permitido": "https://pessoa@github.com/x",
    "usuario_e_senha_em_dominio_permitido": "https://pessoa:senha@github.com/x",
    "http_simples": "http://github.com/x",
    "sem_dominio": "https:///x",
    "ip": "https://127.0.0.1/x",
    "mailto_com_https": "https://mailto:x",
}


@pytest.mark.parametrize("endereco", DOMINIOS_FALSOS.values(), ids=DOMINIOS_FALSOS.keys())
def test_endereco_de_link_fora_da_allowlist_de_dominios_e_recusado(endereco):
    assert Regra.LATEX in _regras(tex_com_corpo(f"\\href{{{endereco}}}{{ver}}"))


@pytest.mark.parametrize(
    "endereco",
    ["https://github.com/pessoa", "https://www.github.com/pessoa", "https://GitHub.com/p"],
)
def test_endereco_de_link_de_dominio_permitido_passa(endereco):
    assert _regras(tex_com_corpo(f"\\href{{{endereco}}}{{ver}}")) == []


def test_mailto_continua_valendo():
    assert _regras(tex_com_corpo("\\href{mailto:pessoa@exemplo.invalid}{pessoa}")) == []


def test_dominios_de_link_vem_da_configuracao():
    dados = configuracao_validador().model_dump()
    dados["latex"]["links"]["dominios"] = ["evil.example", "example.invalid"]
    config = configuracao_validador(dados)

    assert _regras(tex_com_corpo("\\href{https://evil.example/x}{ver}"), config) == []
    assert Regra.LATEX in _regras(tex_com_corpo("\\href{https://github.com/x}{ver}"), config)
