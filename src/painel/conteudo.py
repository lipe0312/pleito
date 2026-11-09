from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from src.config import ambiente
from src.conteudo.aprovar import (
    JaDecidida,
    ProjetoNaoAprovado,
    SugestaoInexistente,
    aprovar,
    rejeitar,
)
from src.conteudo.arquivo import ler_blocos, ler_inventario
from src.conteudo.configuracao import ConfiguracaoConteudo, configuracao_conteudo
from src.conteudo.modelo import Bloco
from src.conteudo.sincronizacao import ConfiguracaoSincronizacao, configuracao_sincronizacao
from src.conteudo.sugestoes import Sugestao, Sugestoes, carregar_sugestoes

ORIGEM_GUIA = "guia"
TIPO_ANCORA_PROJETO = "projeto"
TIPO_BLOCO_PROJETO = "projeto"
STATUS_PENDENTE = "pendente"
STATUS_APROVADA = "aprovada"
ESQUEMA_PUBLICO = "https"


class DecisaoRecusada(Exception):
    def __init__(self, chave: str) -> None:
        super().__init__(chave)
        self.chave = chave


@dataclass(frozen=True, slots=True)
class ProjetoDoBloco:
    id: str
    nome: str
    descricao: str
    link: str
    link_clicavel: bool
    origem: str
    techs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SugestaoPendente:
    id: str
    tipo: str
    origem: str
    nome: str
    url: str
    descricao: str
    tech: str
    evidencias: tuple[str, ...]


class RepositorioConteudo(Protocol):
    def projetos(self) -> list[ProjetoDoBloco]: ...

    def sugestoes_pendentes(self) -> list[SugestaoPendente]: ...

    def aprovar(self, ident: str, por: str, agora: datetime) -> None: ...

    def rejeitar(self, ident: str, por: str, motivo: str, agora: datetime) -> None: ...


def _texto(bloco: Bloco, campo: str, idiomas: list[str]) -> str:
    por_idioma = bloco.imutavel.get(campo, {})
    return next((por_idioma[i] for i in idiomas if i in por_idioma), "")


class RepositorioArquivosConteudo:
    def __init__(self, pasta_dados: Path | None = None) -> None:
        self._dados = pasta_dados if pasta_dados is not None else ambiente().dados
        self._config: ConfiguracaoConteudo = configuracao_conteudo()
        self._sinc: ConfiguracaoSincronizacao = configuracao_sincronizacao()

    def _sugestoes(self) -> Sugestoes | None:
        return carregar_sugestoes(self._dados, self._config, self._sinc)

    def _hosts_conhecidos(self) -> dict[str, str]:
        hosts = {urlparse(self._sinc.github.url_publica).hostname: "github"}
        hosts.update({str(host).lower(): "portfolio" for host in self._sinc.portfolio.dominios})
        return {host: origem for host, origem in hosts.items() if host}

    def _origem(self, bloco: Bloco, link: str, aprovadas: dict[str, str]) -> str:
        if bloco.id in aprovadas:
            return aprovadas[bloco.id]
        return self._hosts_conhecidos().get(urlparse(link).hostname or "", ORIGEM_GUIA)

    def projetos(self) -> list[ProjetoDoBloco]:
        blocos = ler_blocos(self._dados, self._config)
        if blocos is None:
            return []
        inventario = ler_inventario(self._dados, self._config)
        sugestoes = self._sugestoes()
        aprovadas = {
            s.projeto.id: s.origem
            for s in (sugestoes.sugestoes if sugestoes else [])
            if s.status == STATUS_APROVADA
        }
        techs: dict[str, list[str]] = {}
        for item in inventario.techs if inventario else []:
            for ancora in item.ancoras:
                if ancora.tipo == TIPO_ANCORA_PROJETO:
                    techs.setdefault(ancora.ref, []).append(item.tech)
        idiomas = [self._config.idioma_principal, *blocos.idiomas]
        projetos = []
        for bloco in blocos.blocos:
            if bloco.tipo != TIPO_BLOCO_PROJETO:
                continue
            link = _texto(bloco, "link", idiomas)
            origem = self._origem(bloco, link, aprovadas)
            publico = urlparse(link).scheme == ESQUEMA_PUBLICO and origem != ORIGEM_GUIA
            projetos.append(
                ProjetoDoBloco(
                    id=bloco.id,
                    nome=_texto(bloco, "nome", idiomas) or bloco.id,
                    descricao=_texto(bloco, "descricao", idiomas),
                    link=link,
                    link_clicavel=publico and urlparse(link).hostname in self._hosts_conhecidos(),
                    origem=origem,
                    techs=tuple(techs.get(bloco.id, ())),
                )
            )
        return projetos

    def sugestoes_pendentes(self) -> list[SugestaoPendente]:
        sugestoes = self._sugestoes()
        return [
            _pendente(s)
            for s in (sugestoes.sugestoes if sugestoes else [])
            if s.status == STATUS_PENDENTE
        ]

    def aprovar(self, ident: str, por: str, agora: datetime) -> None:
        self._decidir(lambda: aprovar(ident, por, agora, self._dados, self._config, self._sinc))

    def rejeitar(self, ident: str, por: str, motivo: str, agora: datetime) -> None:
        if not motivo.strip():
            raise DecisaoRecusada("motivo_vazio")
        self._decidir(
            lambda: rejeitar(ident, por, motivo, agora, self._dados, self._config, self._sinc)
        )

    @staticmethod
    def _decidir(acao) -> None:
        try:
            acao()
        except SugestaoInexistente as erro:
            raise DecisaoRecusada("inexistente") from erro
        except JaDecidida as erro:
            raise DecisaoRecusada("ja_decidida") from erro
        except ProjetoNaoAprovado as erro:
            raise DecisaoRecusada("projeto_nao_aprovado") from erro
        except ValueError as erro:
            raise DecisaoRecusada("invalida") from erro


def _pendente(sugestao: Sugestao) -> SugestaoPendente:
    return SugestaoPendente(
        id=sugestao.id,
        tipo=sugestao.tipo,
        origem=sugestao.origem,
        nome=sugestao.projeto.nome,
        url=sugestao.projeto.url,
        descricao=sugestao.projeto.descricao,
        tech=sugestao.tech or "",
        evidencias=tuple(sugestao.evidencias),
    )
