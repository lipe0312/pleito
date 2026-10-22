from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Etapa(StrEnum):
    APLICADA = "aplicada"
    TESTE = "teste"
    ENTREVISTA = "entrevista"
    OFERTA = "oferta"
    ENCERRADA = "encerrada"
    CLASSIFICAR = "classificar"
    SUSPEITO = "suspeito"


@dataclass(frozen=True, slots=True)
class Email:
    remetente: str
    assunto: str
    corpo: str
    reply_to: str = ""
    autenticacao: str = ""


@dataclass(frozen=True, slots=True)
class Classificacao:
    etapa: Etapa
    confianca: float
    motivo: Motivo
    plataforma: str | None = None
    gatilho_manual: bool = False
    sugestao: Etapa | None = None


class Motivo(StrEnum):
    DOMINIO_FORA_DO_ASCII = "dominio_fora_do_ascii"
    DOMINIO_IMITA_PLATAFORMA = "dominio_imita_plataforma"
    NOME_DE_EXIBICAO_DE_PLATAFORMA = "nome_de_exibicao_de_plataforma"
    REPLY_TO_DIVERGENTE = "reply_to_divergente"
    REPLY_TO_IMITA_PLATAFORMA = "reply_to_imita_plataforma"
    AUTENTICACAO_NAO_APROVADA = "autenticacao_nao_aprovada"
    SEM_PADRAO = "sem_padrao"
    AMBIGUO = "ambiguo"
    ABAIXO_DO_LIMIAR = "abaixo_do_limiar"
    RECONHECIDO = "reconhecido"
