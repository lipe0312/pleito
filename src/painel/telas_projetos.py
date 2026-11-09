from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from src.config import carregar
from src.painel.conteudo import (
    ProjetoDoBloco,
    RepositorioConteudo,
    SugestaoPendente,
)
from src.painel.curriculos import Curriculo, RepositorioCurriculos
from src.painel.renderizar import HtmlSeguro, juntar, modelo, renderizar
from src.painel.telas import (
    CLASSE_NEUTRA,
    Contexto,
    lista_ou_vazio,
    momento_local,
    montar_pagina,
    montar_selo,
)
from src.painel.telas_curriculos import rota_do_curriculo, secao

SEPARADOR = ", "
CLASSE_ATENCAO = "atencao"
CLASSE_OK = "ok"


def _origem(origem: str) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["projetos"]
    return montar_selo(CLASSE_NEUTRA, textos.get(f"origem_{origem}", origem))


def _link(curriculo: Curriculo) -> HtmlSeguro:
    return renderizar(
        modelo("link_interno.html"), rota=rota_do_curriculo(curriculo), texto=curriculo.titulo
    )


def _usado_em(projeto: ProjetoDoBloco, curriculos: list[Curriculo]) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["projetos"]
    usam = [c for c in curriculos if projeto.id in c.projetos]
    if not usam:
        return renderizar(modelo("quando_texto.html"), texto=textos["nao_usado"])
    return HtmlSeguro(SEPARADOR.join(_link(c) for c in usam))


def _endereco(projeto: ProjetoDoBloco) -> HtmlSeguro | str:
    if projeto.link_clicavel:
        return renderizar(modelo("link_externo.html"), url=projeto.link, texto=projeto.link)
    return projeto.link


def _item_projeto(projeto: ProjetoDoBloco, curriculos: list[Curriculo]) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["projetos"]
    return renderizar(
        modelo("item_projeto.html"),
        nome=projeto.nome,
        descricao=projeto.descricao or textos["sem_descricao"],
        link=_endereco(projeto),
        rotulo_techs=textos["techs"],
        techs=SEPARADOR.join(projeto.techs) or textos["sem_techs"],
        rotulo_usado=textos["usado_em"],
        usado=_usado_em(projeto, curriculos),
        selos=_origem(projeto.origem),
    )


def _titulo_da_sugestao(sugestao: SugestaoPendente) -> str:
    return SEPARADOR.join(parte for parte in (sugestao.nome, sugestao.tech) if parte)


def _selos_da_sugestao(sugestao: SugestaoPendente) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["projetos"]
    return juntar(
        [
            montar_selo(CLASSE_ATENCAO, textos.get(f"tipo_{sugestao.tipo}", sugestao.tipo)),
            _origem(sugestao.origem),
        ]
    )


def item_sugestao(sugestao: SugestaoPendente, erro: str = "") -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["projetos"]
    base = f"/sugestoes/{quote(sugestao.id, safe='')}"
    aviso = (
        renderizar(modelo("aviso_erro.html"), texto=erro) if erro else HtmlSeguro("")
    )
    return renderizar(
        modelo("item_sugestao.html"),
        id=sugestao.id,
        titulo=_titulo_da_sugestao(sugestao),
        descricao=sugestao.descricao or textos["sem_descricao"],
        url=sugestao.url,
        rotulo_evidencias=textos["evidencias"],
        evidencias=SEPARADOR.join(sugestao.evidencias),
        efeito=textos.get(f"efeito_{sugestao.tipo}", ""),
        rota_aprovar=f"{base}/aprovar",
        rota_rejeitar=f"{base}/rejeitar",
        aprovar=textos["aprovar"],
        rotulo_motivo=textos["motivo"],
        motivo_max=configuracao["motivo_max_chars"],
        rejeitar=textos["rejeitar"],
        erro=aviso,
        efeito_rejeitar=textos["efeito_rejeitar"],
        selos=_selos_da_sugestao(sugestao),
    )


def item_decidido(
    sugestao: SugestaoPendente | None,
    ident: str,
    resultado: str,
    classe: str,
    rotulo_selo: str,
) -> HtmlSeguro:
    return renderizar(
        modelo("item_decisao.html"),
        classe=classe,
        id=ident,
        titulo=_titulo_da_sugestao(sugestao) if sugestao else ident,
        resultado=resultado,
        selos=montar_selo(classe, rotulo_selo),
    )


def texto_da_decisao(status: str, por: str, quando: datetime, motivo: str | None) -> str:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["projetos"]
    momento = momento_local(quando).strftime(configuracao["formato_data"])
    return textos[status].format(por=por, quando=momento, motivo=motivo or "")


def pagina_projetos(
    conteudo: RepositorioConteudo, curriculos: RepositorioCurriculos, contexto: Contexto
) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["projetos"]
    pendentes = conteudo.sugestoes_pendentes()
    projetos = conteudo.projetos()
    todos = curriculos.curriculos()
    corpo = juntar(
        [
            renderizar(modelo("titulo_pagina.html"), titulo=textos["titulo"]),
            secao(
                "sugestoes",
                textos["sugestoes"],
                lista_ou_vazio([item_sugestao(s) for s in pendentes], textos["sem_sugestoes"]),
                len(pendentes),
            ),
            secao(
                "projetos",
                textos["blocos"],
                lista_ou_vazio([_item_projeto(p, todos) for p in projetos], textos["sem_projetos"]),
                len(projetos),
            ),
        ]
    )
    return montar_pagina(contexto, "projetos", textos["titulo"], corpo)
