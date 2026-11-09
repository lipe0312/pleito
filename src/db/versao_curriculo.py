from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from psycopg.types.json import Jsonb

TAMANHO_HASH_PDF = 32

SQL_REGISTRAR = """
INSERT INTO versao_curriculo (
    vaga_id, familia, idioma, numero, caminho_tex, caminho_pdf, hash_pdf, paginas,
    linhas_livres, validacao, prompt_versao, modelo, origem
)
SELECT %s, %s::familia, %s::idioma, COALESCE(MAX(numero), 0) + 1, %s, %s, %s, %s,
       %s, %s, %s, %s, %s::origem_versao
FROM versao_curriculo
WHERE vaga_id = %s
RETURNING id, numero
"""

SQL_HISTORICO = """
SELECT id, numero, nivel::text, origem::text, hash_pdf, prompt_versao, modelo, caminho_pdf,
       validacao, paginas, criada_em, aprovada, enviada
FROM historico_versao_curriculo
WHERE vaga_id = %s
ORDER BY numero
"""


class Origem(StrEnum):
    GERADA = "gerada"
    REFEITA = "refeita"
    CHAT = "chat"


@dataclass(frozen=True, slots=True)
class NovaVersao:
    vaga_id: int
    familia: str
    idioma: str
    caminho_tex: str
    caminho_pdf: str
    hash_pdf: bytes
    paginas: int
    prompt_versao: str
    modelo: str
    origem: Origem | str
    linhas_livres: float | None = None
    validacao: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class RegistroVersao:
    id: int
    numero: int


@dataclass(frozen=True, slots=True)
class VersaoHistorico:
    id: int
    numero: int
    nivel: str
    origem: Origem
    hash_pdf: bytes
    prompt_versao: str
    modelo: str
    caminho_pdf: str
    validacao: Mapping[str, object]
    paginas: int
    criada_em: object
    aprovada: bool
    enviada: bool


def registrar_versao(conexao, versao: NovaVersao) -> RegistroVersao:
    origem = Origem(versao.origem)
    if len(versao.hash_pdf) != TAMANHO_HASH_PDF:
        raise ValueError("hash do PDF precisa ser um SHA-256 de 32 bytes")
    with conexao.cursor() as cursor:
        cursor.execute(
            SQL_REGISTRAR,
            (
                versao.vaga_id,
                versao.familia,
                versao.idioma,
                versao.caminho_tex,
                versao.caminho_pdf,
                versao.hash_pdf,
                versao.paginas,
                versao.linhas_livres,
                Jsonb(dict(versao.validacao or {})),
                versao.prompt_versao,
                versao.modelo,
                origem.value,
                versao.vaga_id,
            ),
        )
        identificador, numero = cursor.fetchone()
    return RegistroVersao(id=identificador, numero=numero)


def historico_da_vaga(conexao, vaga_id: int) -> list[VersaoHistorico]:
    with conexao.cursor() as cursor:
        cursor.execute(SQL_HISTORICO, (vaga_id,))
        linhas = cursor.fetchall()
    return [
        VersaoHistorico(
            id=linha[0],
            numero=linha[1],
            nivel=linha[2],
            origem=Origem(linha[3]),
            hash_pdf=bytes(linha[4]),
            prompt_versao=linha[5],
            modelo=linha[6],
            caminho_pdf=linha[7],
            validacao=linha[8],
            paginas=linha[9],
            criada_em=linha[10],
            aprovada=linha[11],
            enviada=linha[12],
        )
        for linha in linhas
    ]
