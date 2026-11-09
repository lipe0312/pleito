from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.coletor.alertas_cartao import Cartao, CartaoDescartado, extrair_cartoes
from src.coletor.alertas_config import ConfiguracaoAlertas, PlataformaAlertas, configuracao_alertas
from src.email.classificador import tem_padrao_de_etapa
from src.email.modelo import Email
from src.email.regras import Regras, normalizar, regras
from src.email.remetente import (
    autenticacao_aprovada,
    caixa_de,
    dominio_exato_da_plataforma,
    motivo_forjado,
)


class TipoAlerta(StrEnum):
    ALERTA_VAGA = "alerta_vaga"
    ALERTA_VAZIO = "alerta_vazio"
    RETORNO = "retorno"
    MENSAGEM_RECRUTADOR = "mensagem_recrutador"
    SUSPEITO = "suspeito"
    OUTRO = "outro"


class RegraGatilho(StrEnum):
    REMETENTE_SUSPEITO = "1_remetente_suspeito"
    CAIXA_NUNCA_VAGA = "2_caixa_nunca_vaga"
    ETAPA_RETORNO = "3_etapa_retorno"
    ASSUNTO_NUNCA_VAGA = "4_assunto_nunca_vaga"
    ALERTA_COM_CARTAO = "5_alerta_com_cartao"
    ALERTA_SEM_CARTAO = "6_alerta_sem_cartao"
    RESTO = "7_resto"


@dataclass(frozen=True, slots=True)
class ResultadoAlerta:
    tipo: TipoAlerta
    regra: RegraGatilho
    plataforma: str
    cartoes: tuple[Cartao, ...] = ()
    descartados: tuple[CartaoDescartado, ...] = ()
    assunto_de_alerta: bool = False


def plataforma_mencionada(
    email: Email, alertas: ConfiguracaoAlertas | None = None, configuradas: Regras | None = None
) -> PlataformaAlertas | None:
    alertas = alertas or configuracao_alertas()
    configuradas = configuradas or regras()
    texto = normalizar(f"{email.remetente} {email.reply_to}")
    for nome, plataforma in alertas.plataformas.items():
        marcas = configuradas.plataformas[nome].marcas
        if any(marca in texto for marca in marcas):
            return plataforma
    return None


def _suspeito(email: Email, plataforma: PlataformaAlertas, configuradas: Regras) -> bool:
    return (
        not dominio_exato_da_plataforma(email.remetente, plataforma.nome, configuradas)
        or not autenticacao_aprovada(email.autenticacao, configuradas)
        or motivo_forjado(email, configuradas) is not None
    )


def _contem(texto: str, termos: tuple[str, ...]) -> bool:
    return any(termo in texto for termo in termos)


def classificar_alerta(
    email: Email,
    plataforma: PlataformaAlertas,
    configuradas: Regras | None = None,
    corpo_max_chars: int | None = None,
) -> ResultadoAlerta:
    configuradas = configuradas or regras()
    limite = corpo_max_chars or configuracao_alertas().corpo_max_chars
    nome = plataforma.nome
    assunto = normalizar(email.assunto)
    caixa = caixa_de(email.remetente)

    def decidir(tipo: TipoAlerta, regra: RegraGatilho, **resto) -> ResultadoAlerta:
        return ResultadoAlerta(
            tipo,
            regra,
            nome,
            assunto_de_alerta=_contem(assunto, plataforma.assunto_alerta),
            **resto,
        )

    if _suspeito(email, plataforma, configuradas):
        return decidir(TipoAlerta.SUSPEITO, RegraGatilho.REMETENTE_SUSPEITO)
    if caixa in plataforma.caixas_nunca_vaga:
        tipo = (
            TipoAlerta.MENSAGEM_RECRUTADOR
            if caixa in plataforma.caixas_mensagem_recrutador
            else TipoAlerta.OUTRO
        )
        return decidir(tipo, RegraGatilho.CAIXA_NUNCA_VAGA)
    if tem_padrao_de_etapa(email, configuradas):
        return decidir(TipoAlerta.RETORNO, RegraGatilho.ETAPA_RETORNO)
    if _contem(assunto, plataforma.assunto_nunca_vaga):
        return decidir(TipoAlerta.OUTRO, RegraGatilho.ASSUNTO_NUNCA_VAGA)
    if caixa in plataforma.caixas_alerta:
        achados = extrair_cartoes(email.corpo, plataforma, limite)
        if achados.completos:
            return decidir(
                TipoAlerta.ALERTA_VAGA,
                RegraGatilho.ALERTA_COM_CARTAO,
                cartoes=achados.completos,
                descartados=achados.descartados,
            )
        return decidir(
            TipoAlerta.ALERTA_VAZIO,
            RegraGatilho.ALERTA_SEM_CARTAO,
            descartados=achados.descartados,
        )
    return decidir(TipoAlerta.OUTRO, RegraGatilho.RESTO)
