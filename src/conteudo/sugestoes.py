from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import model_validator

from src.conteudo.arquivo import PERMISSAO_PASTA, DestinoForaDeDados, destino_conteudo, escrever
from src.conteudo.configuracao import ConfiguracaoConteudo
from src.conteudo.modelo import Ancora, Estrito, Identificador, TextoNaoVazio
from src.conteudo.sincronizacao import ConfiguracaoSincronizacao

TipoSugestao = Literal["projeto_novo", "tecnologia_nova", "projeto_arquivado", "projeto_sumido"]
StatusSugestao = Literal["pendente", "aprovada", "rejeitada"]
Origem = Literal["github", "portfolio"]
PREFIXO_URL_PUBLICA = "https://"


class ProjetoSugerido(Estrito):
    id: Identificador
    nome: TextoNaoVazio
    url: TextoNaoVazio
    descricao: str = ""
    topics: list[str] = []
    linguagens: list[str] = []
    homepage: str | None = None
    pushed_at: str | None = None

    @model_validator(mode="after")
    def _url_publica(self) -> ProjetoSugerido:
        if not self.url.startswith(PREFIXO_URL_PUBLICA):
            raise ValueError(f"url do projeto precisa ser https: {self.url!r}")
        return self


class Sugestao(Estrito):
    id: Identificador
    tipo: TipoSugestao
    status: StatusSugestao = "pendente"
    origem: Origem
    projeto: ProjetoSugerido
    tech: TextoNaoVazio | None = None
    ancora: Ancora | None = None
    ja_no_inventario: bool = False
    evidencias: list[str] = []
    vista_em: TextoNaoVazio
    decidida_por: str | None = None
    decidida_em: str | None = None
    motivo: str | None = None

    @model_validator(mode="after")
    def _tecnologia_tem_ancora_de_projeto_com_url(self) -> Sugestao:
        if self.tipo != "tecnologia_nova":
            return self
        if self.tech is None or self.ancora is None:
            raise ValueError("tecnologia sugerida exige tech e ancora")
        if self.ancora.tipo != "projeto" or self.ancora.ref != self.projeto.id:
            raise ValueError("ancora da tecnologia precisa ser do tipo projeto e do projeto")
        if not self.ancora.fonte.startswith(PREFIXO_URL_PUBLICA):
            raise ValueError("ancora da tecnologia precisa apontar a URL publica")
        return self


class Sugestoes(Estrito):
    geradas_em: TextoNaoVazio
    completo: bool = True
    avisos: list[str] = []
    sugestoes: list[Sugestao] = []


def identificador_sugestao(tipo: str, projeto_id: str, tech: str | None) -> str:
    chave = f"{tipo}|{projeto_id}|{tech or ''}".encode()
    return f"sug_{hashlib.sha256(chave).hexdigest()[:12]}"


def caminho_sugestoes(
    pasta_dados: Path, config: ConfiguracaoConteudo, sinc: ConfiguracaoSincronizacao
) -> Path:
    destino = destino_conteudo(pasta_dados, config)
    if Path(sinc.arquivo_sugestoes).name != sinc.arquivo_sugestoes:
        raise DestinoForaDeDados(f"nome de arquivo invalido: {sinc.arquivo_sugestoes!r}")
    return destino / sinc.arquivo_sugestoes


def carregar_sugestoes(
    pasta_dados: Path, config: ConfiguracaoConteudo, sinc: ConfiguracaoSincronizacao
) -> Sugestoes | None:
    caminho = caminho_sugestoes(pasta_dados, config, sinc)
    if not caminho.is_file():
        return None
    return Sugestoes.model_validate(yaml.safe_load(caminho.read_text(encoding="utf-8")))


def gravar_sugestoes(
    sugestoes: Sugestoes,
    pasta_dados: Path,
    config: ConfiguracaoConteudo,
    sinc: ConfiguracaoSincronizacao,
) -> Path:
    caminho = caminho_sugestoes(pasta_dados, config, sinc)
    caminho.parent.mkdir(parents=True, exist_ok=True, mode=PERMISSAO_PASTA)
    escrever(caminho, sugestoes)
    return caminho
