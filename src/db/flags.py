from __future__ import annotations

from src.db.auditoria import registrar_auditoria
from src.db.conexao import conectar


class SistemaDesativado(RuntimeError):
    pass


def ler_flag(chave: str) -> bool:
    with conectar("app") as conexao, conexao.cursor() as cursor:
        cursor.execute("SELECT ligada FROM flag_sistema WHERE chave = %s", (chave,))
        registro = cursor.fetchone()
    if registro is None:
        raise KeyError(f"flag de sistema desconhecida: {chave}")
    return registro[0]


def exigir_sistema_ativo() -> None:
    if not ler_flag("sistema_ativo"):
        raise SistemaDesativado("sistema desativado pela flag de controle")


def alterar_flag(chave: str, ligada: bool, motivo: str, ator: str = "painel") -> None:
    with conectar("painel") as conexao, conexao.cursor() as cursor:
        cursor.execute(
            "SELECT ligada, motivo FROM flag_sistema WHERE chave = %s FOR UPDATE",
            (chave,),
        )
        antes = cursor.fetchone()
        if antes is None:
            raise KeyError(f"flag de sistema desconhecida: {chave}")
        cursor.execute(
            """
            UPDATE flag_sistema
            SET ligada = %s, motivo = %s
            WHERE chave = %s
            RETURNING chave, ligada, motivo
            """,
            (ligada, motivo, chave),
        )
        depois = cursor.fetchone()
        registrar_auditoria(
            conexao,
            ator=ator,
            acao="alterar_flag",
            entidade="flag_sistema",
            entidade_id=depois[0],
            antes={"ligada": antes[0], "motivo": antes[1]},
            depois={"ligada": depois[1], "motivo": depois[2]},
        )
