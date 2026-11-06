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
