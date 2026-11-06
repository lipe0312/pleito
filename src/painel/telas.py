from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.config import carregar
from src.painel.renderizar import HtmlSeguro, juntar, modelo, renderizar
from src.painel.repositorio import (
    Candidatura,
    EventoDoDia,
    PendenciaAberta,
    RepositorioLeitura,
    UltimoEvento,
)

CLASSE_NEUTRA = "neutro"


@dataclass(frozen=True, slots=True)
class Contexto:
    csrf_cabecalho: str
    csrf_token: str
    ficticio: bool
    agora: datetime


def _fuso() -> ZoneInfo:
    return ZoneInfo(carregar("painel")["fuso"])


def _local(momento: datetime) -> datetime:
    return momento.astimezone(_fuso())


def _selo(classe: str, texto: str) -> HtmlSeguro:
    return renderizar(modelo("selo.html"), classe=classe, texto=texto)


def _tipo(tipo: str) -> tuple[str, str]:
    conhecido = carregar("painel")["tipos_evento"].get(tipo)
    if conhecido is None:
        return tipo, CLASSE_NEUTRA
    return conhecido["rotulo"], conhecido["classe"]


def _lista_ou_vazio(itens: list[HtmlSeguro], texto_vazio: str) -> HtmlSeguro:
    if not itens:
        return renderizar(modelo("vazio.html"), texto=texto_vazio)
    return renderizar(modelo("lista.html"), itens=juntar(itens))


def _meta(*partes: str | None) -> str:
    return " · ".join(parte for parte in partes if parte)


def _pagina(contexto: Contexto, atual: str, titulo: str, conteudo: HtmlSeguro) -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]
    navegacao = juntar(
        [
            renderizar(
                modelo("nav_item.html"),
                rota=item["rota"],
                rotulo=item["rotulo"],
                atual="page" if item["chave"] == atual else "false",
            )
            for item in configuracao["navegacao"]
        ]
    )
    aviso = (
        renderizar(modelo("aviso.html"), texto=textos["comum"]["ficticio"])
        if contexto.ficticio
        else HtmlSeguro("")
    )
    return renderizar(
        modelo("base.html"),
        titulo=titulo,
        pagina=textos["pagina"],
        csrf_cabecalho=contexto.csrf_cabecalho,
        csrf_token=contexto.csrf_token,
        rotulo_navegacao=textos["comum"]["navegacao"],
        navegacao=navegacao,
        aviso=aviso,
        conteudo=conteudo,
    )


def _item_evento(evento: EventoDoDia) -> HtmlSeguro:
    configuracao = carregar("painel")
    comum = configuracao["textos"]["comum"]
    rotulo, classe = _tipo(evento.tipo)
    selos = [_selo(classe, rotulo)]
    if not evento.autenticado:
        selos.append(_selo("atencao", comum["nao_autenticado"]))
    if evento.fila and evento.fila != evento.tipo:
        fila_rotulo, fila_classe = _tipo(evento.fila)
        selos.append(_selo(fila_classe, fila_rotulo))
    momento = _local(evento.recebido_em)
    return renderizar(
        modelo("item_evento.html"),
        classe=classe,
        iso=momento.isoformat(),
        hora=momento.strftime(configuracao["formato_hora"]),
        titulo=evento.vaga or comum["sem_vaga"],
        meta=_meta(evento.empresa, evento.remetente),
        selos=juntar(selos),
    )


def _item_pendencia(pendencia: PendenciaAberta) -> HtmlSeguro:
    configuracao = carregar("painel")
    momento = _local(pendencia.criada_em)
    return renderizar(
        modelo("item_pendencia.html"),
        iso=momento.isoformat(),
        quando=momento.strftime(configuracao["formato_data"]),
        categoria=pendencia.categoria,
        detalhe=pendencia.detalhe,
        meta=_meta(pendencia.vaga, pendencia.empresa),
    )


def pagina_hoje(repositorio: RepositorioLeitura, contexto: Contexto) -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["hoje"]
    agora = _local(contexto.agora)
    inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    eventos = repositorio.eventos_do_dia(inicio, inicio + timedelta(days=1))
    pendencias = repositorio.pendencias_abertas()
    conteudo = renderizar(
        modelo("hoje.html"),
        titulo=textos["titulo"],
        dia=agora.strftime(configuracao["formato_dia"]),
        rotulo_eventos=textos["eventos"],
        total_eventos=len(eventos),
        eventos=_lista_ou_vazio([_item_evento(e) for e in eventos], textos["sem_eventos"]),
        rotulo_pendencias=textos["pendencias"],
        total_pendencias=len(pendencias),
        pendencias=_lista_ou_vazio(
            [_item_pendencia(p) for p in pendencias], textos["sem_pendencias"]
        ),
    )
    return _pagina(contexto, "hoje", textos["titulo"], conteudo)


def _ultimo_evento(ultimo: UltimoEvento | None) -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["candidaturas"]
    if ultimo is None:
        return renderizar(modelo("sem_ultimo_evento.html"), texto=textos["sem_evento"])
    rotulo, classe = _tipo(ultimo.tipo)
    momento = _local(ultimo.recebido_em)
    return renderizar(
        modelo("ultimo_evento.html"),
        rotulo=textos["ultimo_evento"],
        selo=_selo(classe, rotulo),
        iso=momento.isoformat(),
        quando=momento.strftime(configuracao["formato_data"]),
        remetente=ultimo.remetente,
    )


def _item_candidatura(candidatura: Candidatura) -> HtmlSeguro:
    comum = carregar("painel")["textos"]["comum"]
    ultimo = candidatura.ultimo_evento
    classe = _tipo(ultimo.tipo)[1] if ultimo else CLASSE_NEUTRA
    return renderizar(
        modelo("item_candidatura.html"),
        classe=classe,
        titulo=candidatura.titulo,
        empresa=candidatura.empresa or comum["sem_empresa"],
        ultimo=_ultimo_evento(ultimo),
    )


def pagina_candidaturas(repositorio: RepositorioLeitura, contexto: Contexto) -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["candidaturas"]
    etapas = configuracao["etapas_candidatura"]
    candidaturas = repositorio.candidaturas([etapa["estado"] for etapa in etapas])
    por_estado: dict[str, list[Candidatura]] = defaultdict(list)
    for candidatura in candidaturas:
        por_estado[candidatura.estado].append(candidatura)
    secoes = [
        renderizar(
            modelo("secao_etapa.html"),
            estado=etapa["estado"],
            rotulo=etapa["rotulo"],
            total=len(por_estado[etapa["estado"]]),
            itens=_lista_ou_vazio([_item_candidatura(c) for c in por_estado[etapa["estado"]]], ""),
        )
        for etapa in etapas
        if por_estado[etapa["estado"]]
    ]
    corpo = (
        juntar(secoes)
        if secoes
        else renderizar(modelo("vazio.html"), texto=textos["vazio"])
    )
    conteudo = renderizar(modelo("candidaturas.html"), titulo=textos["titulo"], etapas=corpo)
    return _pagina(contexto, "candidaturas", textos["titulo"], conteudo)


def pagina_erro(contexto: Contexto) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["erro"]
    conteudo = renderizar(modelo("erro.html"), titulo=textos["titulo"], corpo=textos["corpo"])
    return _pagina(contexto, "", textos["titulo"], conteudo)
