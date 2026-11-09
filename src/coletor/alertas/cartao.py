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
    url: str
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


def limpar(linha: str) -> str:
    return re.sub(r"\s+", " ", linha).strip()


def linhas_do_corpo(corpo: str, corpo_max_chars: int) -> list[str]:
    return [limpar(linha) for linha in (corpo or "")[:corpo_max_chars].split("\n")]


def campo_ou_vazio(valor: str, plataforma: PlataformaAlertas) -> str:
    if valor.startswith(plataforma.separador_cartao) or "://" in valor:
        return ""
    return valor


def achado_de_vaga(linha: str, plataforma: PlataformaAlertas) -> re.Match[str] | None:
    achado = plataforma.link_vaga.search(linha)
    if achado and any(rotulo in normalizar(linha) for rotulo in plataforma.rotulos_link):
        return achado
    return None


def _motivo_de_descarte(campos: dict, plataforma: PlataformaAlertas) -> str | None:
    for nome in plataforma.cartao_minimo:
        if not campos.get(nome):
            return f"{nome}_ausente"
    if any(termo in normalizar(campos.get("titulo", "")) for termo in plataforma.ruido):
        return "titulo_ruido"
    return None


class Acumulador:
    def __init__(self, plataforma: PlataformaAlertas) -> None:
        self.plataforma = plataforma
        self.completos: list[Cartao] = []
        self.descartados: list[CartaoDescartado] = []
        self.vistos: set[str] = set()

    def adicionar(self, achado: re.Match[str], campos: dict) -> None:
        id_vaga = achado.group("id")
        if id_vaga in self.vistos:
            return
        self.vistos.add(id_vaga)
        motivo = _motivo_de_descarte(campos, self.plataforma)
        if motivo:
            self.descartados.append(CartaoDescartado(id_vaga, motivo))
            return
        self.completos.append(
            Cartao(
                id_vaga,
                self.plataforma.url_da_vaga(achado),
                campos.get("titulo", ""),
                campos.get("empresa", ""),
                campos.get("local", ""),
            )
        )

    def resultado(self) -> ResultadoCartoes:
        return ResultadoCartoes(tuple(self.completos), tuple(self.descartados))


def vaga_do_cartao(
    cartao: Cartao, plataforma: PlataformaAlertas, recebido_em: date | None
) -> VagaBruta:
    limites = plataforma.limites_campos
    contexto = f"{cartao.titulo} {cartao.local}"
    return VagaBruta(
        fonte=plataforma.fonte,
        id_externo=cartao.id_vaga,
        url=cartao.url,
        titulo=cartao.titulo[: limites["titulo"]],
        empresa=cartao.empresa[: limites["empresa"]],
        descricao="",
        local=cartao.local[: limites["local"]],
        pais=inferir_pais(cartao.local) or plataforma.pais_padrao,
        senioridade=inferir_senioridade(cartao.titulo),
        modelo=inferir_modelo(contexto),
        funcao=inferir_funcao(cartao.titulo),
        anos_experiencia=extrair_anos_experiencia(cartao.titulo),
        publicada_em=recebido_em,
    )
