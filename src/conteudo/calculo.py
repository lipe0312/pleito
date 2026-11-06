from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from src.conteudo.modelo import Ancora, Blocos, Inventario
from src.conteudo.sincronizacao import ConfiguracaoSincronizacao
from src.conteudo.sugestoes import (
    Origem,
    ProjetoSugerido,
    Sugestao,
    Sugestoes,
    identificador_sugestao,
)


@dataclass(frozen=True, slots=True)
class ProjetoLido:
    projeto: ProjetoSugerido
    origem: Origem
    evidencias: dict[str, list[str]]


def normalizar_url(url: str) -> str:
    sem_esquema = url.strip().lower().removeprefix("https://").removeprefix("http://")
    return sem_esquema.removeprefix("www.").rstrip("/").removesuffix(".git").rstrip("/")


def _blocos_de_projeto(blocos: Blocos | None) -> dict[str, str]:
    if blocos is None:
        return {}
    return {
        normalizar_url(link): bloco.id
        for bloco in blocos.blocos
        if bloco.tipo == "projeto"
        for link in bloco.imutavel.get("link", {}).values()
    }


def _sugestao(tipo, origem, projeto, agora, **campos) -> Sugestao:
    return Sugestao(
        id=identificador_sugestao(tipo, projeto.id, campos.get("tech")),
        tipo=tipo,
        origem=origem,
        projeto=projeto,
        vista_em=agora.isoformat(),
        **campos,
    )


def _sugestoes_do_projeto(
    lido: ProjetoLido, por_url: dict[str, str], inventario: Inventario | None, agora: datetime
) -> list[Sugestao]:
    existente = por_url.get(normalizar_url(lido.projeto.url))
    projeto = lido.projeto.model_copy(update={"id": existente or lido.projeto.id})
    sugestoes = []
    if existente is None:
        sugestoes.append(_sugestao("projeto_novo", lido.origem, projeto, agora))
    itens = {i.tech.lower(): i for i in inventario.techs} if inventario else {}
    for tech, evidencias in sorted(lido.evidencias.items()):
        item = itens.get(tech.lower())
        if item and any(a.tipo == "projeto" and a.ref == projeto.id for a in item.ancoras):
            continue
        sugestoes.append(
            _sugestao(
                "tecnologia_nova",
                lido.origem,
                projeto,
                agora,
                tech=item.tech if item else tech,
                ancora=Ancora(tipo="projeto", ref=projeto.id, fonte=projeto.url),
                ja_no_inventario=item is not None,
                evidencias=evidencias,
            )
        )
    return sugestoes


def _sugestoes_de_revisao(
    config: ConfiguracaoSincronizacao,
    blocos: Blocos | None,
    vistos: dict[str, bool],
    completo: bool,
    agora: datetime,
) -> list[Sugestao]:
    if blocos is None:
        return []
    base = urlsplit(config.github.url_publica).netloc.lower()
    prefixo = f"{base}/{config.github.usuario.lower()}/"
    sugestoes = []
    for bloco in blocos.blocos:
        if bloco.tipo != "projeto":
            continue
        for link in bloco.imutavel.get("link", {}).values():
            normal = normalizar_url(link)
            nome = normal.removeprefix(prefixo)
            if not normal.startswith(prefixo) or "/" in nome:
                continue
            projeto = ProjetoSugerido(id=bloco.id, nome=nome, url=f"https://{normal}")
            if nome in vistos and vistos[nome] and config.github.ignorar_arquivado:
                sugestoes.append(_sugestao("projeto_arquivado", "github", projeto, agora))
            elif nome not in vistos and completo:
                sugestoes.append(_sugestao("projeto_sumido", "github", projeto, agora))
            break
    return sugestoes


def calcular_sugestoes(
    config: ConfiguracaoSincronizacao,
    lidos: list[ProjetoLido],
    vistos: dict[str, bool],
    blocos: Blocos | None,
    inventario: Inventario | None,
    anteriores: Sugestoes | None,
    completo: bool,
    avisos: list[str],
    agora: datetime,
) -> Sugestoes:
    historico = [s for s in anteriores.sugestoes if s.status != "pendente"] if anteriores else []
    rejeitados = {s.id for s in historico if s.status == "rejeitada"}
    projetos_rejeitados = {
        s.projeto.id for s in historico if s.status == "rejeitada" and s.tipo == "projeto_novo"
    }
    por_url = _blocos_de_projeto(blocos)
    novas: list[Sugestao] = []
    for lido in lidos:
        novas += _sugestoes_do_projeto(lido, por_url, inventario, agora)
    novas += _sugestoes_de_revisao(config, blocos, vistos, completo, agora)
    novas = [s for s in novas if s.id not in rejeitados and s.projeto.id not in projetos_rejeitados]
    ids_novas = {s.id for s in novas}
    mantidas = [s for s in historico if s.id not in ids_novas]
    return Sugestoes(
        geradas_em=agora.isoformat(),
        completo=completo,
        avisos=avisos,
        sugestoes=[*mantidas, *novas],
    )
