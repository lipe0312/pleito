from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from psycopg.types.json import Jsonb

from src.db.auditoria import registrar_auditoria
from src.email.eventos import Decisao, Politica, decidir, politica
from src.email.modelo import Classificacao, Email, Etapa
from src.email.remetente import autenticacao_aprovada, dominio_de, endereco_de

SQL_ESTADO_VAGA = "SELECT estado::text FROM vaga WHERE id = %s FOR UPDATE"
SQL_EVENTO = """
INSERT INTO evento_email (
    vaga_id, id_mensagem, remetente, dominio, autenticado, tipo, confianca, payload,
    recebido_em, fila
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id_mensagem) DO NOTHING
RETURNING id
"""
SQL_MUDAR_ESTADO = "UPDATE vaga SET estado = %s::estado_vaga WHERE id = %s"
SQL_APLICAR = "UPDATE evento_email SET aplicado = true WHERE id = %s"
CENTESIMO = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class EmailRecebido:
    id_mensagem: str
    email: Email
    recebido_em: datetime


@dataclass(frozen=True, slots=True)
class ResultadoEvento:
    evento_id: int | None
    duplicado: bool
    decisao: Decisao | None = None
    estado_anterior: str | None = None


def _autenticado(email: Email, classificacao: Classificacao) -> bool:
    return classificacao.etapa is not Etapa.SUSPEITO and autenticacao_aprovada(email.autenticacao)


def _confianca(valor: float) -> Decimal:
    return Decimal(str(valor)).quantize(CENTESIMO, rounding=ROUND_DOWN)


def _texto(valor: str) -> str:
    return valor.replace("\x00", "")


def _estado_atual(cursor, vaga_id: int | None) -> str | None:
    if vaga_id is None:
        return None
    cursor.execute(SQL_ESTADO_VAGA, (vaga_id,))
    linha = cursor.fetchone()
    return linha[0] if linha else None


def gravar_evento(
    conexao,
    recebido: EmailRecebido,
    classificacao: Classificacao,
    vaga_id: int | None = None,
    configurada: Politica | None = None,
) -> ResultadoEvento:
    configurada = configurada or politica()
    autenticado = _autenticado(recebido.email, classificacao)
    with conexao.cursor() as cursor:
        estado_anterior = _estado_atual(cursor, vaga_id)
        vinculada = vaga_id if estado_anterior is not None else None
        decisao = decidir(classificacao, autenticado, estado_anterior, configurada)
        fila = decisao.fila.value if decisao.fila else None
        confianca = _confianca(classificacao.confianca)
        payload = {
            "motivo": decisao.motivo.value,
            "motivo_classificacao": classificacao.motivo.value,
            "plataforma": classificacao.plataforma,
            "sugestao": classificacao.sugestao.value if classificacao.sugestao else None,
            "gatilho_manual": classificacao.gatilho_manual,
        }
        cursor.execute(
            SQL_EVENTO,
            (
                vinculada,
                _texto(recebido.id_mensagem),
                _texto(endereco_de(recebido.email.remetente)),
                _texto(dominio_de(recebido.email.remetente)) or None,
                autenticado,
                classificacao.etapa.value,
                confianca,
                Jsonb(payload),
                recebido.recebido_em,
                fila,
            ),
        )
        linha = cursor.fetchone()
        if linha is None:
            return ResultadoEvento(evento_id=None, duplicado=True)
        evento_id = linha[0]
        registrar_auditoria(
            conexao,
            configurada.ator,
            "registrar_evento",
            "evento_email",
            str(evento_id),
            depois={
                "tipo": classificacao.etapa.value,
                "confianca": str(confianca),
                "autenticado": autenticado,
                "fila": fila,
                "motivo": decisao.motivo.value,
                "vaga_id": vinculada,
            },
        )
        if decisao.fila is not None:
            return ResultadoEvento(evento_id, False, decisao, estado_anterior)
        if decisao.estado_novo is not None:
            cursor.execute(SQL_MUDAR_ESTADO, (decisao.estado_novo, vinculada))
            registrar_auditoria(
                conexao,
                configurada.ator,
                "mudar_estado",
                "vaga",
                str(vinculada),
                antes={"estado": estado_anterior},
                depois={"estado": decisao.estado_novo, "evento_email_id": evento_id},
            )
        cursor.execute(SQL_APLICAR, (evento_id,))
        registrar_auditoria(
            conexao,
            configurada.ator,
            "aplicar_evento",
            "evento_email",
            str(evento_id),
            antes={"aplicado": False},
            depois={"aplicado": True},
        )
    return ResultadoEvento(evento_id, False, decisao, estado_anterior)
