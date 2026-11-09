from __future__ import annotations

from urllib.parse import quote

from src.config import carregar
from src.painel.curriculos import (
    BASE_ANTERIOR,
    BASE_FAMILIA,
    BASE_NENHUMA,
    TIPO_FAMILIA,
    TIPO_VAGA,
    Curriculo,
    LinhaDeDiff,
    RepositorioCurriculos,
    VersaoPublicada,
    Violacao,
)
from src.painel.renderizar import HtmlSeguro, juntar, modelo, renderizar
from src.painel.telas import (
    CLASSE_NEUTRA,
    Contexto,
    juntar_meta,
    lista_ou_vazio,
    momento_local,
    montar_pagina,
    montar_selo,
)

CLASSE_ERRO = "erro"


def rota_do_curriculo(curriculo: Curriculo) -> str:
    base = carregar("painel")["curriculos"]["rota"]
    return f"{base}/{curriculo.tipo}/{quote(curriculo.id, safe='')}"


def rota_do_pdf(curriculo: Curriculo) -> str:
    prefixo = carregar("painel")["pdf"]["prefixo_rota"]
    return f"{prefixo}{curriculo.tipo}/{quote(curriculo.id, safe='')}"


def _custo(curriculo: Curriculo) -> str:
    casas = carregar("painel")["curriculos"]["casas_custo"]
    valor = f"{curriculo.custo_usd:.{casas}f}".replace(".", ",")
    return carregar("painel")["textos"]["curriculos"]["custo"].format(valor=valor)


def _tentativas(curriculo: Curriculo) -> str:
    textos = carregar("painel")["textos"]["curriculos"]
    if curriculo.tentativas == 1:
        return textos["tentativa_um"]
    return textos["tentativa_varias"].format(n=curriculo.tentativas)


def _selos(curriculo: Curriculo) -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["curriculos"]
    situacao = curriculo.situacao
    classe = configuracao["curriculos"]["classe_da_situacao"].get(situacao, CLASSE_NEUTRA)
    return juntar(
        [
            montar_selo(classe, textos[situacao]),
            montar_selo(CLASSE_NEUTRA, _tentativas(curriculo)),
            montar_selo(CLASSE_NEUTRA, _custo(curriculo)),
        ]
    )


def _quando(versao: VersaoPublicada) -> HtmlSeguro:
    configuracao = carregar("painel")
    if versao.criada_em is None:
        return renderizar(
            modelo("quando_texto.html"), texto=configuracao["textos"]["curriculos"]["sem_data"]
        )
    momento = momento_local(versao.criada_em)
    return renderizar(
        modelo("quando_data.html"),
        iso=momento.isoformat(),
        texto=momento.strftime(configuracao["formato_data"]),
    )


def _meta_da_lista(curriculo: Curriculo) -> str:
    if not curriculo.versoes:
        return ""
    ultima = curriculo.versoes[-1]
    configuracao = carregar("painel")
    quando = (
        momento_local(ultima.criada_em).strftime(configuracao["formato_data"])
        if ultima.criada_em
        else configuracao["textos"]["curriculos"]["sem_data"]
    )
    rotulo = configuracao["textos"]["curriculo"]["versao"].format(
        versao=ultima.versao, tentativa=ultima.tentativa
    )
    if curriculo.tipo == TIPO_VAGA:
        return juntar_meta(f"{ultima.familia} ({ultima.idioma})", rotulo, quando)
    return juntar_meta(rotulo, quando)


def _item(curriculo: Curriculo) -> HtmlSeguro:
    classe = carregar("painel")["curriculos"]["classe_da_situacao"].get(
        curriculo.situacao, CLASSE_NEUTRA
    )
    return renderizar(
        modelo("item_curriculo.html"),
        classe=classe if classe == CLASSE_ERRO else CLASSE_NEUTRA,
        rota=rota_do_curriculo(curriculo),
        titulo=curriculo.titulo,
        meta=_meta_da_lista(curriculo),
        selos=_selos(curriculo),
    )


def secao(chave: str, rotulo: str, itens: HtmlSeguro, total: int | None = None) -> HtmlSeguro:
    contagem = (
        renderizar(modelo("contagem.html"), total=total) if total is not None else HtmlSeguro("")
    )
    return renderizar(
        modelo("secao.html"), chave=chave, rotulo=rotulo, contagem=contagem, itens=itens
    )


def pagina_curriculos(repositorio: RepositorioCurriculos, contexto: Contexto) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["curriculos"]
    todos = repositorio.curriculos()
    familias = [c for c in todos if c.tipo == TIPO_FAMILIA]
    vagas = [c for c in todos if c.tipo == TIPO_VAGA]
    conteudo = juntar(
        [
            renderizar(modelo("titulo_pagina.html"), titulo=textos["titulo"]),
            secao(
                "familias",
                textos["familias"],
                lista_ou_vazio([_item(c) for c in familias], textos["sem_familias"]),
                len(familias),
            ),
            secao(
                "vagas",
                textos["vagas"],
                lista_ou_vazio([_item(c) for c in vagas], textos["sem_vagas"]),
                len(vagas),
            ),
        ]
    )
    return montar_pagina(contexto, "curriculos", textos["titulo"], conteudo)


def _violacao(violacao: Violacao) -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["curriculo"]
    classe = configuracao["curriculos"]["niveis_de_selo"].get(violacao.nivel, CLASSE_NEUTRA)
    rotulo = textos.get(f"nivel_{violacao.nivel}", violacao.nivel)
    trecho = (
        renderizar(modelo("linha_trecho.html"), texto=violacao.trecho)
        if violacao.trecho
        else HtmlSeguro("")
    )
    sugestao = (
        renderizar(
            modelo("linha_sugestao.html"), rotulo=textos["sugestao"], texto=violacao.sugestao
        )
        if violacao.sugestao
        else HtmlSeguro("")
    )
    return renderizar(
        modelo("violacao.html"),
        classe=classe,
        codigo=violacao.codigo,
        regra=violacao.regra,
        detalhe=violacao.detalhe,
        trecho=trecho,
        sugestao=sugestao,
        selo=montar_selo(classe, rotulo),
    )


def _lado(linhas: tuple[str, ...], sinal: str) -> HtmlSeguro:
    return juntar([renderizar(modelo("linha_diff.html"), sinal=sinal, texto=t) for t in linhas])


def _slot_do_diff(linha: LinhaDeDiff) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["curriculo"]
    sinais = carregar("painel")["curriculos"]["sinais_do_diff"]
    return renderizar(
        modelo("diff_slot.html"),
        nome=linha.nome,
        rotulo_saiu=textos["saiu"],
        rotulo_entrou=textos["entrou"],
        saiu=_lado(linha.saiu, sinais["saiu"]),
        entrou=_lado(linha.entrou, sinais["entrou"]),
    )


def _base_do_diff(curriculo: Curriculo) -> str:
    textos = carregar("painel")["textos"]["curriculo"]
    if curriculo.base_tipo == BASE_FAMILIA:
        return textos["base_familia"].format(base=curriculo.base_rotulo)
    if curriculo.base_tipo == BASE_ANTERIOR:
        return textos["base_anterior"]
    return textos["base_nenhuma"]


def _diff(curriculo: Curriculo) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["curriculo"]
    base = renderizar(modelo("linha_base.html"), texto=_base_do_diff(curriculo))
    if curriculo.diff:
        itens = juntar([_slot_do_diff(d) for d in curriculo.diff])
        return juntar([base, renderizar(modelo("lista_diff.html"), itens=itens)])
    if curriculo.base_tipo == BASE_NENHUMA:
        return base
    return juntar([base, renderizar(modelo("vazio.html"), texto=textos["sem_mudanca"])])


def _versao(versao: VersaoPublicada) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["curriculo"]
    return renderizar(
        modelo("item_versao.html"),
        quando=_quando(versao),
        titulo=textos["versao"].format(versao=versao.versao, tentativa=versao.tentativa),
        meta=juntar_meta(
            f"{versao.familia} ({versao.idioma})", versao.motivo or textos["sem_motivo"]
        ),
    )


def _pdf(curriculo: Curriculo) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["curriculo"]
    if not curriculo.tem_pdf:
        return renderizar(modelo("vazio.html"), texto=textos["sem_pdf"])
    return renderizar(
        modelo("pdf_embutido.html"),
        origem=rota_do_pdf(curriculo),
        titulo=textos["titulo_pdf"].format(titulo=curriculo.titulo),
        abrir=textos["abrir_pdf"],
    )


def _regras(curriculo: Curriculo) -> HtmlSeguro:
    textos = carregar("painel")["textos"]["curriculo"]
    if curriculo.violacoes is None:
        return renderizar(modelo("vazio.html"), texto=textos["sem_validacao"])
    return lista_ou_vazio([_violacao(v) for v in curriculo.violacoes], textos["sem_violacoes"])


def pagina_curriculo(curriculo: Curriculo, contexto: Contexto) -> HtmlSeguro:
    configuracao = carregar("painel")
    textos = configuracao["textos"]["curriculo"]
    secoes = juntar(
        [
            secao("pdf", textos["pdf"], _pdf(curriculo)),
            secao("regras", textos["regras"], _regras(curriculo)),
            secao("diff", textos["diff"], _diff(curriculo)),
            secao(
                "versoes",
                textos["versoes"],
                lista_ou_vazio(
                    [_versao(v) for v in reversed(curriculo.versoes)], textos["sem_versoes"]
                ),
                len(curriculo.versoes),
            ),
        ]
    )
    conteudo = renderizar(
        modelo("curriculo.html"),
        rota_lista=configuracao["curriculos"]["rota"],
        voltar=textos["voltar"],
        titulo=curriculo.titulo,
        meta=_meta_da_lista(curriculo),
        selos=_selos(curriculo),
        secoes=secoes,
    )
    return montar_pagina(contexto, "curriculos", curriculo.titulo, conteudo)
