from __future__ import annotations

from src.email.modelo import Classificacao, Email, Etapa, Motivo
from src.email.regras import PadroesEtapa, Regras, normalizar, regras
from src.email.remetente import motivo_forjado, plataforma_de


def _pontos(
    padroes: PadroesEtapa, assunto: str, corpo: str, configuradas: Regras
) -> float:
    no_assunto = any(termo in assunto for termo in padroes.assunto)
    no_corpo = any(termo in corpo for termo in padroes.corpo)
    if not (no_assunto or no_corpo):
        return 0.0
    falta_assunto = 1 - (configuradas.peso_assunto if no_assunto else 0.0)
    falta_corpo = 1 - (configuradas.peso_corpo if no_corpo else 0.0)
    return 1 - falta_assunto * falta_corpo


def classificar(email: Email, configuradas: Regras | None = None) -> Classificacao:
    configuradas = configuradas or regras()
    motivo = motivo_forjado(email, configuradas)
    if motivo:
        return Classificacao(Etapa.SUSPEITO, configuradas.confianca_suspeito, motivo)

    plataforma = None
    if email.autenticacao.strip():
        plataforma = plataforma_de(email.remetente, configuradas)
    assunto = normalizar(email.assunto)
    corpo = normalizar((email.corpo or "")[: configuradas.corpo_max_chars])

    pontuadas = sorted(
        (
            (_pontos(padroes, assunto, corpo, configuradas), etapa)
            for etapa, padroes in configuradas.etapas.items()
        ),
        key=lambda par: par[0],
        reverse=True,
    )
    pontuadas = [par for par in pontuadas if par[0] > 0]
    if not pontuadas:
        return Classificacao(Etapa.CLASSIFICAR, 0.0, Motivo.SEM_PADRAO, plataforma)

    melhor, etapa = pontuadas[0]
    if len(pontuadas) > 1 and melhor - pontuadas[1][0] < configuradas.margem_ambiguidade:
        return Classificacao(Etapa.CLASSIFICAR, melhor, Motivo.AMBIGUO, plataforma)

    confianca = melhor
    if plataforma is None:
        confianca = min(melhor, configuradas.confianca_remetente_desconhecido_max)
    if confianca < configuradas.limiar_confianca:
        return Classificacao(
            Etapa.CLASSIFICAR, confianca, Motivo.ABAIXO_DO_LIMIAR, plataforma, sugestao=etapa
        )

    gatilho = (
        etapa is Etapa.APLICADA
        and plataforma is not None
        and any(
            termo in assunto
            for termo in configuradas.plataformas[plataforma].gatilho_candidatura
        )
    )
    return Classificacao(etapa, confianca, Motivo.RECONHECIDO, plataforma, gatilho_manual=gatilho)
