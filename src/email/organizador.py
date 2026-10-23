from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx

from src.config import ambiente, carregar
from src.email.classificador import classificar, tem_padrao_de_etapa
from src.email.cursor import Cursor, gravar_cursor, ler_cursor
from src.email.mensagem import email_de_mensagem
from src.email.modelo import Classificacao, Email, Etapa, Motivo
from src.email.regras import Regras, normalizar, regras
from src.email.remetente import plataforma_de
from src.email.rotulos import resolver_rotulos

MOTIVOS_DE_IMITACAO = frozenset(
    {
        Motivo.DOMINIO_IMITA_PLATAFORMA,
        Motivo.NOME_DE_EXIBICAO_DE_PLATAFORMA,
        Motivo.REPLY_TO_DIVERGENTE,
        Motivo.REPLY_TO_IMITA_PLATAFORMA,
    }
)


class Caixa(Protocol):
    def rotulos(self) -> list[dict]: ...
    def perfil(self) -> dict: ...
    def listar(self, consulta: str, maximo: int) -> list[dict]: ...
    def historico(self, inicio: str, rotulo: str, pagina: str | None = None) -> dict: ...
    def ler(self, identificador: str) -> dict: ...
    def rotular(self, identificador: str, adicionar: list[str], remover: list[str]) -> dict: ...
    def arquivar(self, identificador: str) -> dict: ...


@dataclass(frozen=True, slots=True)
class ConfiguracaoOrganizacao:
    caminho_cursor: Path
    consulta_inicial: str
    lote_inicial: int
    intervalo: timedelta
    manter_na_caixa: frozenset[Etapa]
    rotulo_caixa_entrada: str


@dataclass(slots=True)
class Resumo:
    adiada: bool = False
    por_etapa: dict[Etapa, int] = field(default_factory=dict)
    ignoradas: int = 0
    fora_da_caixa: int = 0


def configuracao_organizacao(
    caminho_cursor: Path | None = None, manter_na_caixa: list[str] | None = None
) -> ConfiguracaoOrganizacao:
    emails = carregar("emails")
    bruto = emails["organizacao"]
    minutos = carregar("limites")["horarios"]["email_intervalo_min"]
    return ConfiguracaoOrganizacao(
        caminho_cursor=caminho_cursor or ambiente().dados / bruto["cursor"],
        consulta_inicial=bruto["consulta_inicial"],
        lote_inicial=int(bruto["lote_inicial"]),
        intervalo=timedelta(minutes=float(minutos)),
        manter_na_caixa=frozenset(
            Etapa(nome)
            for nome in (
                bruto["manter_na_caixa"] if manter_na_caixa is None else manter_na_caixa
            )
        ),
        rotulo_caixa_entrada=emails["gmail"]["rotulo_caixa_entrada"],
    )


def _menciona_plataforma(email: Email, configuradas: Regras) -> bool:
    texto = normalizar(f"{email.remetente} {email.reply_to}")
    return any(
        marca in texto
        for plataforma in configuradas.plataformas.values()
        for marca in plataforma.marcas
    )


def _de_plataforma_de_vagas(email: Email, configuradas: Regras) -> bool:
    plataforma = plataforma_de(email.remetente, configuradas)
    return plataforma is not None and plataforma != configuradas.plataforma_alertas


def relevante(email: Email, classificacao: Classificacao, configuradas: Regras) -> bool:
    if classificacao.motivo in MOTIVOS_DE_IMITACAO or tem_padrao_de_etapa(email, configuradas):
        return True
    if classificacao.etapa is Etapa.SUSPEITO:
        return _menciona_plataforma(email, configuradas)
    return _de_plataforma_de_vagas(email, configuradas)


def _historico_expirado(erro: httpx.HTTPStatusError) -> bool:
    return erro.response.status_code == httpx.codes.NOT_FOUND


def _ids_do_inicio(caixa: Caixa, cfg: ConfiguracaoOrganizacao) -> tuple[list[str], str]:
    inicio = str(caixa.perfil()["historyId"])
    ids = [item["id"] for item in caixa.listar(cfg.consulta_inicial, cfg.lote_inicial)]
    return ids, inicio


def _ids_do_historico(
    caixa: Caixa, cursor: Cursor, cfg: ConfiguracaoOrganizacao
) -> tuple[list[str], str]:
    vistos: dict[str, None] = {}
    novo = cursor.history_id
    pagina = None
    while True:
        resposta = caixa.historico(cursor.history_id, cfg.rotulo_caixa_entrada, pagina)
        for registro in resposta.get("history", []):
            for adicionada in registro.get("messagesAdded", []):
                vistos.setdefault(adicionada["message"]["id"], None)
        novo = str(resposta.get("historyId", novo))
        pagina = resposta.get("nextPageToken")
        if not pagina:
            return list(vistos), novo


def ids_novos(
    caixa: Caixa, cursor: Cursor | None, cfg: ConfiguracaoOrganizacao
) -> tuple[list[str], str]:
    if cursor is None:
        return _ids_do_inicio(caixa, cfg)
    try:
        return _ids_do_historico(caixa, cursor, cfg)
    except httpx.HTTPStatusError as erro:
        if not _historico_expirado(erro):
            raise
        return _ids_do_inicio(caixa, cfg)


def organizar_mensagem(
    caixa: Caixa,
    mensagem: dict,
    rotulos: dict[Etapa, str],
    cfg: ConfiguracaoOrganizacao,
    configuradas: Regras,
) -> Etapa | None:
    email = email_de_mensagem(mensagem)
    classificacao = classificar(email, configuradas)
    if not relevante(email, classificacao, configuradas):
        return None
    destino = rotulos[classificacao.etapa]
    das_etapas = set(rotulos.values())
    anteriores = [
        rotulo
        for rotulo in mensagem.get("labelIds", [])
        if rotulo in das_etapas and rotulo != destino
    ]
    caixa.rotular(mensagem["id"], [destino], anteriores)
    if classificacao.etapa not in cfg.manter_na_caixa:
        caixa.arquivar(mensagem["id"])
    return classificacao.etapa


def rodada(
    caixa: Caixa,
    cfg: ConfiguracaoOrganizacao,
    agora: datetime,
    forcar: bool = False,
    configuradas: Regras | None = None,
) -> Resumo:
    cursor = ler_cursor(cfg.caminho_cursor)
    if not forcar and cursor is not None and agora - cursor.ultima_leitura < cfg.intervalo:
        return Resumo(adiada=True)
    configuradas = configuradas or regras()
    rotulos = resolver_rotulos(caixa)
    ids, novo = ids_novos(caixa, cursor, cfg)
    contagem: Counter[Etapa] = Counter()
    resumo = Resumo()
    for identificador in ids:
        mensagem = caixa.ler(identificador)
        if cfg.rotulo_caixa_entrada not in mensagem.get("labelIds", []):
            resumo.fora_da_caixa += 1
            continue
        etapa = organizar_mensagem(caixa, mensagem, rotulos, cfg, configuradas)
        if etapa is None:
            resumo.ignoradas += 1
        else:
            contagem[etapa] += 1
    resumo.por_etapa = dict(contagem)
    gravar_cursor(cfg.caminho_cursor, Cursor(novo, agora))
    return resumo
