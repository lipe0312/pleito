from __future__ import annotations

import re

from src.config import RAIZ
from src.gerador.slots import TextoComTechs
from src.padroes.configuracao import configuracao_padroes
from src.padroes.pontuacao import violacoes_de_pontuacao
from src.padroes.rubrica import CurriculoAvaliado, avaliar

CAMINHO = RAIZ / "docs" / "curriculo-padroes.md"
SECOES = [
    "Não invenção",
    "Uma página",
    "Ordem de corte",
    "Idioma",
    "Estrutura do bullet",
    "Senioridade",
    "Pontuação (Q5)",
]


def test_doc_cobre_as_regras_exigidas_cada_uma_uma_vez():
    texto = CAMINHO.read_text(encoding="utf-8")
    titulos = [linha for linha in texto.splitlines() if linha.startswith("## ")]
    for secao in SECOES:
        assert sum(secao in titulo for titulo in titulos) == 1


def test_doc_cita_toda_chave_do_yaml_na_tabela_ou_no_texto():
    texto = CAMINHO.read_text(encoding="utf-8")
    chaves = set(configuracao_padroes().model_dump()) - {"idiomas", "prompt", "marcacao"}
    assert [chave for chave in chaves if f"`{chave}`" not in texto] == []


def test_doc_nao_usa_travessao_nos_exemplos_bons():
    texto = CAMINHO.read_text(encoding="utf-8")
    bons = [linha for linha in texto.splitlines() if linha.startswith("- Bom")]
    assert bons
    assert not any("—" in linha for linha in bons)


EXEMPLO = re.compile(
    r"^- (?P<juizo>Bom|Ruim)(?: \[(?P<tipo>\w+)\])? \(fictício(?:, [^)]+)?\): (?P<resto>.+)$"
)
TECNOLOGIAS = ["Python", "PostgreSQL", "Docker", "GitHub Actions", "Airflow"]
FAMILIA = "backend_arquitetura"


def _exemplos():
    linhas = [
        linha
        for linha in CAMINHO.read_text(encoding="utf-8").splitlines()
        if linha.startswith(("- Bom", "- Ruim"))
    ]
    achados = [(linha, EXEMPLO.match(linha)) for linha in linhas]
    sem_marca = [linha for linha, achado in achados if achado is None]
    assert not sem_marca, f"exemplo sem a marca fictício: {sem_marca}"
    return [achado.groupdict() for _, achado in achados]


def _texto(exemplo: dict) -> str:
    return re.search(r'"(.+)"', exemplo["resto"]).group(1)


def _item(texto: str) -> TextoComTechs:
    return TextoComTechs(texto=texto, techs=[tech for tech in TECNOLOGIAS if tech in texto])


def _nota_do_bullet(texto: str) -> dict[str, float]:
    sobre = TextoComTechs(texto="x", techs=[])
    curriculo = CurriculoAvaliado(sobre=sobre, bullets_por_entrada=[[_item(texto)]])
    return avaliar(configuracao_padroes(), curriculo, "pt", FAMILIA, [], []).notas


def _nota_do_sobre(texto: str) -> dict[str, float]:
    curriculo = CurriculoAvaliado(sobre=_item(texto), bullets_por_entrada=[])
    return avaliar(configuracao_padroes(), curriculo, "pt", FAMILIA, [], []).notas


def test_todo_exemplo_do_doc_tem_juizo_e_marca_ficticio():
    exemplos = _exemplos()
    assert len(exemplos) >= 14
    assert {exemplo["juizo"] for exemplo in exemplos} == {"Bom", "Ruim"}


def test_exemplos_bons_do_doc_passam_e_os_ruins_falham_na_rubrica_e_na_pontuacao():
    config = configuracao_padroes()
    verificados = set()
    for exemplo in _exemplos():
        tipo, bom = exemplo["tipo"], exemplo["juizo"] == "Bom"
        if tipo is None:
            continue
        texto = _texto(exemplo)
        if tipo == "bullet":
            assert (_nota_do_bullet(texto)["bullet_vago"] == 1) is bom, texto
        elif tipo == "sobre":
            notas = _nota_do_sobre(texto)
            assert (notas["sobre_generico"] == 1 and notas["aderencia_familia"] == 1) is bom, texto
        elif tipo == "pontuacao":
            assert (violacoes_de_pontuacao(config, texto) == []) is bom, texto
        else:
            raise AssertionError(f"tipo de exemplo desconhecido: {tipo}")
        verificados.add((tipo, bom))
    assert verificados == {
        (tipo, bom) for tipo in ("bullet", "sobre", "pontuacao") for bom in (True, False)
    }


def test_doc_nao_repete_numero_nem_lista_do_yaml():
    texto = CAMINHO.read_text(encoding="utf-8")
    config = configuracao_padroes()
    assert not re.search(r"\b(60|220|250|450)\b", texto)
    for lista in (config.ordem_de_corte, config.nunca_no_corte, config.nao_invencao):
        assert not any(item in texto for item in lista)
