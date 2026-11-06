from __future__ import annotations

from src.config import RAIZ
from src.padroes.configuracao import configuracao_padroes

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
