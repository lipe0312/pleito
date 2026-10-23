from __future__ import annotations

import re
from dataclasses import dataclass

from src.config import carregar


@dataclass(frozen=True, slots=True)
class ConfiguracaoConteudo:
    subpasta: str
    arquivo_blocos: str
    arquivo_inventario: str
    variavel_guia: str
    secao_base: str
    secao_tecnologias: str
    padrao_equivalencia: re.Pattern[str]
    idioma_principal: str
    idiomas_babel: dict[str, str]
    secoes: dict[str, str]
    prefixos_id: dict[str, str]
    palavras_id_max: int
    fonte_ancora: str


def configuracao_conteudo(dados: dict | None = None) -> ConfiguracaoConteudo:
    bruto = dados if dados is not None else carregar("conteudo")
    destino = bruto["destino"]
    guia = bruto["guia"]
    idiomas_babel = dict(guia["idiomas_babel"])
    if guia["idioma_principal"] not in idiomas_babel.values():
        raise ValueError("idioma_principal precisa estar em idiomas_babel")
    return ConfiguracaoConteudo(
        subpasta=str(destino["subpasta"]),
        arquivo_blocos=str(destino["blocos"]),
        arquivo_inventario=str(destino["inventario"]),
        variavel_guia=str(guia["variavel_ambiente"]),
        secao_base=str(guia["secao_base"]),
        secao_tecnologias=str(guia["secao_tecnologias"]),
        padrao_equivalencia=re.compile(guia["padrao_equivalencia"]),
        idioma_principal=str(guia["idioma_principal"]),
        idiomas_babel=idiomas_babel,
        secoes=dict(guia["secoes"]),
        prefixos_id=dict(guia["prefixos_id"]),
        palavras_id_max=int(guia["palavras_id_max"]),
        fonte_ancora=str(guia["fonte_ancora"]),
    )
