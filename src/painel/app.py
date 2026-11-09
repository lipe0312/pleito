from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

import psycopg
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.config import carregar
from src.db.conexao import ConfiguracaoBancoInvalida
from src.painel.conteudo import DecisaoRecusada, RepositorioArquivosConteudo, RepositorioConteudo
from src.painel.curriculos import RepositorioArquivosCurriculos, RepositorioCurriculos
from src.painel.repositorio import RepositorioBanco, RepositorioFicticio, RepositorioLeitura
from src.painel.seguranca import ProtecaoPainel, gerar_token
from src.painel.telas import Contexto, pagina_candidaturas, pagina_erro, pagina_hoje
from src.painel.telas_curriculos import pagina_curriculo, pagina_curriculos
from src.painel.telas_projetos import (
    item_decidido,
    item_sugestao,
    pagina_projetos,
    texto_da_decisao,
)

ESTATICOS = Path(__file__).resolve().parent / "static"
FALHAS_DE_LEITURA = (psycopg.Error, ConfiguracaoBancoInvalida)
FALHAS_DE_DADOS = (OSError, ValueError, KeyError, TypeError, yaml.YAMLError)
TIPO_PDF = "application/pdf"
CORPO_GRANDE = 413


class CorpoGrande(Exception):
    pass


def _relogio_padrao() -> datetime:
    return datetime.now(ZoneInfo(carregar("painel")["fuso"]))


async def _campos(requisicao: Request, limite: int) -> dict[str, str]:
    corpo = b""
    async for parte in requisicao.stream():
        corpo += parte
        if len(corpo) > limite:
            raise CorpoGrande
    lidos = parse_qs(corpo.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {nome: valores[0] for nome, valores in lidos.items()}


def criar_app(
    repositorio: RepositorioLeitura | None = None,
    relogio: Callable[[], datetime] | None = None,
    curriculos: RepositorioCurriculos | None = None,
    conteudo: RepositorioConteudo | None = None,
) -> FastAPI:
    configuracao = carregar("painel")
    token = gerar_token(configuracao["token_bytes"])
    leitura = repositorio if repositorio is not None else RepositorioBanco()
    dados_de_curriculos = curriculos if curriculos is not None else RepositorioArquivosCurriculos()
    dados_de_conteudo = conteudo if conteudo is not None else RepositorioArquivosConteudo()
    ficticio = isinstance(leitura, RepositorioFicticio)
    agora = relogio or _relogio_padrao
    aplicacao = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    aplicacao.mount("/assets", StaticFiles(directory=ESTATICOS), name="assets")
    textos_projetos = configuracao["textos"]["projetos"]

    def contexto() -> Contexto:
        return Contexto(
            csrf_cabecalho=configuracao["csrf_cabecalho"],
            csrf_token=token,
            ficticio=ficticio,
            agora=agora(),
        )

    def responder(montar: Callable[[Contexto], str], falhas: tuple, chave_de_erro: str):
        atual = contexto()
        try:
            return HTMLResponse(montar(atual))
        except falhas:
            return HTMLResponse(pagina_erro(atual, chave_de_erro), status_code=503)

    def responder_banco(montar: Callable[[RepositorioLeitura, Contexto], str]) -> HTMLResponse:
        return responder(lambda atual: montar(leitura, atual), FALHAS_DE_LEITURA, "erro")

    def responder_dados(montar: Callable[[Contexto], str]) -> HTMLResponse:
        return responder(montar, FALHAS_DE_DADOS, "erro_dados")

    @aplicacao.get("/")
    def inicio() -> RedirectResponse:
        return RedirectResponse(configuracao["rota_inicial"], status_code=303)

    @aplicacao.get("/hoje", response_class=HTMLResponse)
    def hoje() -> HTMLResponse:
        return responder_banco(pagina_hoje)

    @aplicacao.get("/candidaturas", response_class=HTMLResponse)
    def candidaturas() -> HTMLResponse:
        return responder_banco(pagina_candidaturas)

    @aplicacao.get("/curriculos", response_class=HTMLResponse)
    def lista_de_curriculos() -> HTMLResponse:
        return responder_dados(lambda atual: pagina_curriculos(dados_de_curriculos, atual))

    @aplicacao.get("/curriculos/{tipo}/{ident}", response_class=HTMLResponse)
    def um_curriculo(tipo: str, ident: str) -> HTMLResponse:
        atual = contexto()
        try:
            achado = next(
                (c for c in dados_de_curriculos.curriculos() if (c.tipo, c.id) == (tipo, ident)),
                None,
            )
            if achado is not None:
                return HTMLResponse(pagina_curriculo(achado, atual))
        except FALHAS_DE_DADOS:
            return HTMLResponse(pagina_erro(atual, "erro_dados"), status_code=503)
        return HTMLResponse(pagina_erro(atual, "curriculo_nao_encontrado"), status_code=404)

    @aplicacao.get(configuracao["pdf"]["prefixo_rota"] + "{tipo}/{ident}")
    def pdf(tipo: str, ident: str) -> Response:
        try:
            conteudo_do_pdf = dados_de_curriculos.pdf(tipo, ident)
        except FALHAS_DE_DADOS:
            return PlainTextResponse("pdf indisponivel", status_code=503)
        if conteudo_do_pdf is None:
            return PlainTextResponse("pdf nao encontrado", status_code=404)
        return Response(conteudo_do_pdf, media_type=TIPO_PDF)

    @aplicacao.get("/projetos", response_class=HTMLResponse)
    def projetos() -> HTMLResponse:
        return responder_dados(
            lambda atual: pagina_projetos(dados_de_conteudo, dados_de_curriculos, atual)
        )

    def achar(ident: str):
        return next((s for s in dados_de_conteudo.sugestoes_pendentes() if s.id == ident), None)

    def recusar(ident: str, chave: str) -> HTMLResponse:
        texto = textos_projetos["erros"][chave].format(max=configuracao["motivo_max_chars"])
        pendente = achar(ident)
        corpo = (
            item_sugestao(pendente, texto)
            if pendente is not None and chave in {"motivo_vazio", "motivo_longo"}
            else item_decidido(pendente, ident, texto, "atencao", chave_para_rotulo(chave))
        )
        return HTMLResponse(corpo, status_code=configuracao["status_da_decisao"][chave])

    def chave_para_rotulo(chave: str) -> str:
        return textos_projetos["rotulos_de_erro"].get(chave, chave)

    def decidir(ident: str, executar: Callable[[RepositorioConteudo], None], status: str, motivo):
        pendente = achar(ident)
        try:
            executar(dados_de_conteudo)
        except DecisaoRecusada as erro:
            return recusar(ident, erro.chave)
        except FALHAS_DE_DADOS:
            return recusar(ident, "invalida")
        classe = "ok" if status == "aprovada" else "neutro"
        resultado = texto_da_decisao(status, configuracao["aprovador"], agora(), motivo)
        return HTMLResponse(
            item_decidido(pendente, ident, resultado, classe, textos_projetos[f"selo_{status}"])
        )

    @aplicacao.post("/sugestoes/{ident}/aprovar", response_class=HTMLResponse)
    def aprovar(ident: str) -> HTMLResponse:
        return decidir(
            ident,
            lambda repo: repo.aprovar(ident, configuracao["aprovador"], agora()),
            "aprovada",
            None,
        )

    @aplicacao.post("/sugestoes/{ident}/rejeitar", response_class=HTMLResponse)
    async def rejeitar(ident: str, requisicao: Request) -> Response:
        try:
            campos = await _campos(requisicao, configuracao["corpo_max_bytes"])
        except CorpoGrande:
            return PlainTextResponse("corpo grande demais", status_code=CORPO_GRANDE)
        motivo = campos.get("motivo", "").strip()
        if not motivo:
            return recusar(ident, "motivo_vazio")
        if len(motivo) > configuracao["motivo_max_chars"]:
            return recusar(ident, "motivo_longo")
        return decidir(
            ident,
            lambda repo: repo.rejeitar(ident, configuracao["aprovador"], motivo, agora()),
            "rejeitada",
            motivo,
        )

    aplicacao.add_middleware(ProtecaoPainel, token=token)
    return aplicacao


app = criar_app()
