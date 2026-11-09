from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from src.coletor.alertas_config import PlataformaAlertas
from src.coletor.base import inferir_modelo, inferir_pais, inferir_senioridade
from src.coletor.contratos import VagaBruta
from src.email.regras import normalizar
from src.triagem.regra import extrair_anos_experiencia, inferir_funcao


@dataclass(frozen=True, slots=True)
class Cartao:
    id_vaga: str
    titulo: str
    empresa: str
    local: str


@dataclass(frozen=True, slots=True)
class CartaoDescartado:
    id_vaga: str
    motivo: str


@dataclass(frozen=True, slots=True)
class ResultadoCartoes:
    completos: tuple[Cartao, ...] = ()
    descartados: tuple[CartaoDescartado, ...] = ()


def _limpar(linha: str) -> str:
    return re.sub(r"\s+", " ", linha).strip()


def _campo(linha: str, plataforma: PlataformaAlertas) -> str:
    if linha.startswith(plataforma.separador_cartao) or "://" in linha:
        return ""
    return linha


def _campos_do_cartao(linhas: list[str], posicao: int, plataforma: PlataformaAlertas) -> dict:
    nomes = plataforma.cartao_campos
    anteriores = linhas[max(0, posicao - len(nomes)) : posicao]
    anteriores = [""] * (len(nomes) - len(anteriores)) + anteriores
    return {nome: _campo(linha, plataforma) for nome, linha in zip(nomes, anteriores, strict=True)}


def _motivo_de_descarte(campos: dict, plataforma: PlataformaAlertas) -> str | None:
    for nome in plataforma.cartao_minimo:
        if not campos.get(nome):
            return f"{nome}_ausente"
    if any(termo in normalizar(campos.get("titulo", "")) for termo in plataforma.ruido):
        return "titulo_ruido"
    return None


def extrair_cartoes(
    corpo: str, plataforma: PlataformaAlertas, corpo_max_chars: int
) -> ResultadoCartoes:
    linhas = [_limpar(linha) for linha in (corpo or "")[:corpo_max_chars].split("\n")]
    completos: list[Cartao] = []
    descartados: list[CartaoDescartado] = []
    vistos: set[str] = set()
    for posicao, linha in enumerate(linhas):
        achado = plataforma.link_vaga.search(linha)
        if not achado or not any(r in normalizar(linha) for r in plataforma.rotulos_link):
            continue
        id_vaga = achado.group(1)
        if id_vaga in vistos:
            continue
        vistos.add(id_vaga)
        campos = _campos_do_cartao(linhas, posicao, plataforma)
        motivo = _motivo_de_descarte(campos, plataforma)
        if motivo:
            descartados.append(CartaoDescartado(id_vaga, motivo))
            continue
        completos.append(
            Cartao(
                id_vaga,
                campos.get("titulo", ""),
                campos.get("empresa", ""),
                campos.get("local", ""),
            )
        )
    return ResultadoCartoes(tuple(completos), tuple(descartados))


def vaga_do_cartao(
    cartao: Cartao, plataforma: PlataformaAlertas, recebido_em: date | None
) -> VagaBruta:
    limites = plataforma.limites_campos
    contexto = f"{cartao.titulo} {cartao.local}"
    return VagaBruta(
        fonte=plataforma.fonte,
        id_externo=cartao.id_vaga,
        url=plataforma.link_canonico.format(id=cartao.id_vaga),
        titulo=cartao.titulo[: limites['titulo']],
        empresa=cartao.empresa[: limites['empresa']],
        descricao="",
        local=cartao.local[: limites['local']],
        pais=inferir_pais(cartao.local) or plataforma.pais_padrao,
        senioridade=inferir_senioridade(cartao.titulo),
        modelo=inferir_modelo(contexto),
        funcao=inferir_funcao(cartao.titulo),
        anos_experiencia=extrair_anos_experiencia(cartao.titulo),
        publicada_em=recebido_em,
    )
