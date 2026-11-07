from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx

from src.coletor.alertas_cartao import vaga_do_cartao
from src.coletor.alertas_config import ConfiguracaoAlertas, configuracao_alertas
from src.coletor.alertas_gatilho import (
    ResultadoAlerta,
    TipoAlerta,
    classificar_alerta,
    plataforma_mencionada,
)
from src.coletor.contratos import VagaBruta
from src.coletor.repositorio import deduplicar_lote, gravar_vagas
from src.config import ambiente, carregar
from src.email.cursor import Cursor, gravar_cursor, ler_cursor
from src.email.mensagem import email_de_mensagem, recebido_em_de
from src.email.organizador import (
    Caixa,
    ConfiguracaoOrganizacao,
    caminho_do_cursor,
    ids_novos,
)
from src.email.regras import Regras, regras

MODO_DO_REGISTRO = 0o600


class Destino(Protocol):
    def gravar(self, vagas: list[VagaBruta]) -> object: ...


@dataclass(frozen=True, slots=True)
class ConfiguracaoColeta:
    caminho_registro: Path
    organizacao: ConfiguracaoOrganizacao


@dataclass(slots=True)
class ResumoAlertas:
    adiada: bool = False
    lidos: int = 0
    ignorados: int = 0
    repetidos: int = 0
    sumidas: int = 0
    vagas_enviadas: int = 0
    por_tipo: dict[TipoAlerta, int] = field(default_factory=dict)


class DestinoNoBanco:
    def __init__(self, conexao) -> None:
        self.conexao = conexao

    def gravar(self, vagas: list[VagaBruta]):
        try:
            resumo = gravar_vagas(self.conexao, vagas)
            self.conexao.commit()
        except BaseException:
            self.conexao.rollback()
            raise
        return resumo


class RegistroLidos:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho

    def entradas(self) -> list[dict]:
        if not self.caminho.exists():
            return []
        lidas = []
        for linha in self.caminho.read_text(encoding="utf-8").splitlines():
            try:
                entrada = json.loads(linha)
            except ValueError:
                continue
            if isinstance(entrada, dict) and isinstance(entrada.get("id_mensagem"), str):
                lidas.append(entrada)
        return lidas

    def ids(self) -> set[str]:
        return {entrada["id_mensagem"] for entrada in self.entradas()}

    def gravar(self, entradas: list[dict]) -> None:
        if not entradas:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        texto = "".join(json.dumps(entrada, ensure_ascii=False) + "\n" for entrada in entradas)
        descritor = os.open(
            self.caminho, os.O_WRONLY | os.O_APPEND | os.O_CREAT, MODO_DO_REGISTRO
        )
        with os.fdopen(descritor, "a", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        os.chmod(self.caminho, MODO_DO_REGISTRO)


def contagem_por_tipo(caminho: Path, desde: datetime) -> dict[str, int]:
    contagem: Counter[str] = Counter()
    for entrada in RegistroLidos(caminho).entradas():
        try:
            lido_em = datetime.fromisoformat(entrada["lido_em"])
        except (KeyError, TypeError, ValueError):
            continue
        if lido_em >= desde:
            contagem[str(entrada.get("tipo"))] += 1
    return dict(contagem)


def configuracao_coleta(
    caminho_cursor: Path | None = None, caminho_registro: Path | None = None
) -> ConfiguracaoColeta:
    bruto = carregar("alertas")
    dados = ambiente().dados
    minutos = carregar("limites")["horarios"]["alertas_intervalo_min"]
    organizacao = ConfiguracaoOrganizacao(
        caminho_cursor=caminho_cursor or caminho_do_cursor(dados, bruto["cursor"]),
        consulta_inicial=bruto["consulta_inicial"],
        lote_inicial=int(bruto["lote_inicial"]),
        intervalo=timedelta(minutes=float(minutos)),
        manter_na_caixa=frozenset(),
        rotulo_caixa_entrada=carregar("emails")["gmail"]["rotulo_caixa_entrada"],
    )
    return ConfiguracaoColeta(
        caminho_registro=caminho_registro or caminho_do_cursor(dados, bruto["registro"]),
        organizacao=organizacao,
    )


def _ler(caixa: Caixa, identificador: str, resumo: ResumoAlertas) -> dict | None:
    try:
        return caixa.ler(identificador)
    except httpx.HTTPStatusError as erro:
        if erro.response.status_code != httpx.codes.NOT_FOUND:
            raise
        resumo.sumidas += 1
        return None


def _entrada(
    identificador: str, resultado: ResultadoAlerta, recebido: datetime, agora: datetime
) -> dict:
    return {
        "id_mensagem": identificador,
        "plataforma": resultado.plataforma,
        "tipo": resultado.tipo.value,
        "regra": resultado.regra.value,
        "assunto_de_alerta": resultado.assunto_de_alerta,
        "cartoes_completos": len(resultado.cartoes),
        "cartoes_descartados": len(resultado.descartados),
        "motivos_descarte": [d.motivo for d in resultado.descartados],
        "recebido_em": recebido.isoformat(),
        "lido_em": agora.isoformat(),
    }


def rodada_alertas(
    caixa: Caixa,
    cfg: ConfiguracaoColeta,
    agora: datetime,
    destino: Destino,
    forcar: bool = False,
    configuradas: Regras | None = None,
    alertas: ConfiguracaoAlertas | None = None,
) -> ResumoAlertas:
    organizacao = cfg.organizacao
    cursor = ler_cursor(organizacao.caminho_cursor)
    if not forcar and cursor is not None and agora - cursor.ultima_leitura < organizacao.intervalo:
        return ResumoAlertas(adiada=True)
    configuradas = configuradas or regras()
    alertas = alertas or configuracao_alertas()
    ids, novo = ids_novos(caixa, cursor, organizacao)
    registro = RegistroLidos(cfg.caminho_registro)
    ja_lidos = registro.ids()
    resumo = ResumoAlertas()
    entradas: list[dict] = []
    vagas: list[VagaBruta] = []
    contagem: Counter[TipoAlerta] = Counter()
    for identificador in ids:
        if identificador in ja_lidos:
            resumo.repetidos += 1
            continue
        mensagem = _ler(caixa, identificador, resumo)
        if mensagem is None:
            continue
        email = email_de_mensagem(mensagem)
        plataforma = plataforma_mencionada(email, alertas, configuradas)
        if plataforma is None:
            resumo.ignorados += 1
            continue
        resultado = classificar_alerta(email, plataforma, configuradas, alertas.corpo_max_chars)
        recebido = recebido_em_de(mensagem, agora)
        vagas.extend(
            vaga_do_cartao(cartao, plataforma, recebido.date()) for cartao in resultado.cartoes
        )
        entradas.append(_entrada(identificador, resultado, recebido, agora))
        contagem[resultado.tipo] += 1
        resumo.lidos += 1
    unicas = deduplicar_lote(vagas)
    if unicas:
        destino.gravar(unicas)
    resumo.vagas_enviadas = len(unicas)
    resumo.por_tipo = dict(contagem)
    registro.gravar(entradas)
    gravar_cursor(organizacao.caminho_cursor, Cursor(novo, agora))
    return resumo
