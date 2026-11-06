from __future__ import annotations

from pathlib import Path

import yaml

from src.conteudo.configuracao import configuracao_conteudo
from src.conteudo.decompor import decompor
from src.gerador.slots import redacao_para_slot
from src.gerador.travado import Travado

PASTA_FIXTURES = Path(__file__).resolve().parent / "fixtures"
COMANDOS_DE_ESCAPE = {"textbackslash", "textasciicircum", "textasciitilde", "textquotedbl"}
COMANDOS_DE_ESCAPE |= {"textless", "textgreater", "textbar", "textasciigrave"}


ATAQUES = [
    r"\input{/etc/passwd}",
    r"\include{segredo}",
    r"\write18{touch /tmp/x}",
    r"\immediate\write18{touch /tmp/x}",
    r"\openin1=/etc/passwd",
    r"\catcode`\%=12",
    r"\def\x{\input{/etc/passwd}}",
    r"\newcommand{\x}{y}",
    r"\csname input\endcsname{/etc/passwd}",
    r"\usepackage{shellesc}",
    "^^5cinput{/etc/passwd}",
    "^^5c^^5cwrite18{x}",
    "$x^2$ $$y$$",
    "100% seguro",
    "a & b",
    "#1 #2",
    "a_b_c",
    "{",
    "}",
    "}{\\input{x}",
    "~",
    "^",
    "\\",
    "\\\\",
    "\\ ",
    '"a "o "<',
    "<<x>> <%y%> <#z#>",
    "`` ''",
]

CONTROLES = [
    "linha\nnova",
    "linha\rnova",
    "aba\ttab",
    "nulo\x00",
    "escape\x1b[31m",
    "direcao\u202eoculta",
    "largura\u200bzero",
    "separador\u2028linha",
    "bom\ufeffmarca",
    "privado\ue000",
]


def conteudo_ficticio():
    guia = (PASTA_FIXTURES / "guia_ficticio.md").read_text(encoding="utf-8")
    return decompor(guia, configuracao_conteudo())


def travado_ficticio() -> Travado:
    bruto = yaml.safe_load((PASTA_FIXTURES / "travado_ficticio.yaml").read_text(encoding="utf-8"))
    return Travado.model_validate(bruto)


def entrada_do_bloco(bloco, idioma: str) -> dict:
    return {
        "bloco": bloco.id,
        "bullets": [redacao_para_slot(bullet.redacao[idioma]) for bullet in bloco.bullets],
    }


def slots_ficticios(blocos, idioma: str) -> dict:
    por_id = {bloco.id: bloco for bloco in blocos.blocos}
    return {
        "sobre": redacao_para_slot(por_id["sobre"].redacao[idioma]),
        "disciplinas": ["Algoritmos", "Banco de Dados"],
        "experiencias": [
            entrada_do_bloco(por_id["exp_empresa_exemplo_ltda"], idioma),
            entrada_do_bloco(por_id["exp_laboratorio_exemplo_visao"], idioma),
        ],
        "projetos": [entrada_do_bloco(por_id["proj_projeto_alfa_beta"], idioma)],
    }
