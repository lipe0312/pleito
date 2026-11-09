from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from src.config import carregar
from src.email.regras import normalizar

FORMATO_ROTULADO = "bloco_rotulado"


class AlertasMalConfigurado(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlataformaAlertas:
    nome: str
    fonte: str
    formato: str
    pais_padrao: str
    caixas_alerta: tuple[str, ...]
    caixas_nunca_vaga: tuple[str, ...]
    caixas_mensagem_recrutador: tuple[str, ...]
    assunto_alerta: tuple[str, ...]
    assunto_nunca_vaga: tuple[str, ...]
    link_vaga: re.Pattern[str]
    link_canonico: str
    rotulos_link: tuple[str, ...]
    ruido: tuple[str, ...]
    separador_cartao: str
    cartao_campos: tuple[str, ...]
    cartao_minimo: tuple[str, ...]
    limites_campos: dict[str, int]
    rotulos_campos: dict[str, tuple[str, ...]] = field(default_factory=dict)
    exige_assunto_alerta: bool = False

    def url_da_vaga(self, achado: re.Match[str]) -> str:
        return self.link_canonico.format(**achado.groupdict())


@dataclass(frozen=True, slots=True)
class ConfiguracaoAlertas:
    cursor: str
    registro: str
    consulta_inicial: str
    lote_inicial: int
    corpo_max_chars: int
    plataformas: dict[str, PlataformaAlertas]


def _caixas(valores: list[str]) -> tuple[str, ...]:
    return tuple(valor.lower() for valor in valores)


def _textos(valores: list[str]) -> tuple[str, ...]:
    return tuple(normalizar(valor) for valor in valores)


def _formato(nome: str, dados: dict) -> str:
    formato = dados.get("formato")
    if not isinstance(formato, str):
        raise AlertasMalConfigurado(f"{nome}: formato ausente")
    return formato


def _plataforma(nome: str, dados: dict) -> PlataformaAlertas:
    plataforma = PlataformaAlertas(
        nome=nome,
        fonte=dados["fonte"],
        formato=_formato(nome, dados),
        pais_padrao=dados["pais_padrao"],
        caixas_alerta=_caixas(dados["caixas_alerta"]),
        caixas_nunca_vaga=_caixas(dados["caixas_nunca_vaga"]),
        caixas_mensagem_recrutador=_caixas(dados["caixas_mensagem_recrutador"]),
        assunto_alerta=_textos(dados["assunto_alerta"]),
        assunto_nunca_vaga=_textos(dados["assunto_nunca_vaga"]),
        link_vaga=re.compile(dados["link_vaga"]),
        link_canonico=dados["link_canonico"],
        rotulos_link=_textos(dados["rotulos_link"]),
        ruido=_textos(dados["ruido"]),
        separador_cartao=dados["separador_cartao"],
        cartao_campos=tuple(dados["cartao_campos"]),
        cartao_minimo=tuple(dados["cartao_minimo"]),
        limites_campos={nome: int(valor) for nome, valor in dados["limites_campos"].items()},
        exige_assunto_alerta=bool(dados.get("exige_assunto_alerta", False)),
        rotulos_campos={
            campo: _textos(rotulos) for campo, rotulos in dados.get("rotulos_campos", {}).items()
        },
    )
    grupos = set(plataforma.link_vaga.groupindex)
    if "id" not in grupos or "{id}" not in plataforma.link_canonico:
        raise AlertasMalConfigurado(f"{nome}: link_vaga com grupo id e link_canonico com {{id}}")
    if plataforma.link_vaga.groups != len(grupos):
        raise AlertasMalConfigurado(f"{nome}: todo grupo de link_vaga precisa de nome")
    if set(re.findall(r"{(\w+)}", plataforma.link_canonico)) - grupos:
        raise AlertasMalConfigurado(f"{nome}: link_canonico cita campo fora de link_vaga")
    if plataforma.exige_assunto_alerta and not plataforma.assunto_alerta:
        raise AlertasMalConfigurado(f"{nome}: exige_assunto_alerta sem assunto_alerta")
    if not plataforma.formato:
        raise AlertasMalConfigurado(f"{nome}: formato vazio")
    if plataforma.formato == FORMATO_ROTULADO and not set(plataforma.cartao_campos) <= set(
        plataforma.rotulos_campos
    ):
        raise AlertasMalConfigurado(f"{nome}: rotulos_campos sem todos os cartao_campos")
    if not set(plataforma.cartao_minimo) <= set(plataforma.cartao_campos):
        raise AlertasMalConfigurado(f"{nome}: cartao_minimo fora de cartao_campos")
    if not set(plataforma.cartao_campos) <= set(plataforma.limites_campos):
        raise AlertasMalConfigurado(f"{nome}: limites_campos sem todos os cartao_campos")
    if any(limite <= 0 for limite in plataforma.limites_campos.values()):
        raise AlertasMalConfigurado(f"{nome}: limites_campos precisa ser positivo")
    if not set(plataforma.caixas_mensagem_recrutador) <= set(plataforma.caixas_nunca_vaga):
        raise AlertasMalConfigurado(f"{nome}: caixa de recrutador fora de caixas_nunca_vaga")
    if set(plataforma.caixas_alerta) & set(plataforma.caixas_nunca_vaga):
        raise AlertasMalConfigurado(f"{nome}: caixa em alerta e em nunca_vaga")
    return plataforma


def montar(bruto: dict) -> ConfiguracaoAlertas:
    return ConfiguracaoAlertas(
        cursor=bruto["cursor"],
        registro=bruto["registro"],
        consulta_inicial=bruto["consulta_inicial"],
        lote_inicial=int(bruto["lote_inicial"]),
        corpo_max_chars=int(bruto["corpo_max_chars"]),
        plataformas={
            nome: _plataforma(nome, dados) for nome, dados in bruto["plataformas"].items()
        },
    )


@lru_cache(maxsize=1)
def configuracao_alertas() -> ConfiguracaoAlertas:
    return montar(carregar("alertas"))
