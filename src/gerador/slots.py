from __future__ import annotations

from typing import TypeVar

from pydantic import ValidationError

from src.conteudo.decompor import ESCAPE, TECH
from src.conteudo.modelo import Bloco, Blocos, Estrito, Inventario
from src.gerador.configuracao import (
    ConfiguracaoGerador,
    SlotEntradas,
    SlotListaTexto,
    SlotTexto,
)
from src.gerador.erros import SlotAusente, SlotInvalido, SlotNaoDeclarado, TravadoInvalido
from src.gerador.escape import (
    LatexSeguro,
    compor_texto,
    escapar_latex,
    texto_limpo,
    url_segura,
)

M = TypeVar("M", bound=Estrito)


class TextoComTechs(Estrito):
    texto: str
    techs: list[str] = []


class EntradaDeBloco(Estrito):
    bloco: str
    bullets: list[TextoComTechs] = []


def redacao_para_slot(redacao: str) -> dict:
    techs = [ESCAPE.sub(r"\1", tech).strip() for tech in TECH.findall(redacao)]
    texto = ESCAPE.sub(r"\1", TECH.sub(lambda achado: achado.group(1), redacao))
    return {"texto": texto, "techs": list(dict.fromkeys(techs))}


def _validar(modelo: type[M], valor: object, nome: str) -> M:
    try:
        return modelo.model_validate(valor)
    except ValidationError as erro:
        raise SlotInvalido(f"{nome}: formato fora do declarado") from erro


def _lista(valor: object, nome: str, maximo: int) -> list:
    if not isinstance(valor, list):
        raise SlotInvalido(f"{nome}: precisa ser lista")
    if len(valor) > maximo:
        raise SlotInvalido(f"{nome}: {len(valor)} itens, limite {maximo}")
    return valor


def _texto_com_techs(
    valor: object, max_chars: int, permitidas: frozenset[str], nome: str
) -> LatexSeguro:
    item = _validar(TextoComTechs, valor, nome)
    limpo = texto_limpo(item.texto, max_chars, nome)
    return compor_texto(limpo, item.techs, permitidas)


def _fatos(bloco: Bloco, idioma: str, config: ConfiguracaoGerador) -> dict:
    contexto: dict[str, LatexSeguro] = {}
    for campo, por_idioma in bloco.imutavel.items():
        if idioma not in por_idioma:
            raise TravadoInvalido(f"bloco {bloco.id}: {campo} sem texto em {idioma!r}")
        nome = f"{bloco.id}.{campo}"
        texto = texto_limpo(
            ESCAPE.sub(r"\1", por_idioma[idioma]), config.travado.texto_max_chars, nome
        )
        contexto[campo] = LatexSeguro(escapar_latex(texto))
        if campo in config.travado.campos_url:
            endereco = url_segura(texto, config.travado.padrao_url, nome)
            visivel = endereco.removeprefix(config.travado.prefixo_url_oculto)
            contexto[f"{campo}_url"] = LatexSeguro(endereco)
            contexto[f"{campo}_texto"] = LatexSeguro(escapar_latex(visivel))
    return contexto


def _entradas(
    nome: str,
    valor: object,
    declaracao: SlotEntradas,
    idioma: str,
    config: ConfiguracaoGerador,
    blocos: Blocos,
    permitidas: frozenset[str],
) -> list[dict]:
    por_id = {bloco.id: bloco for bloco in blocos.blocos}
    usados: set[str] = set()
    saida = []
    for posicao, bruto in enumerate(_lista(valor, nome, declaracao.max_entradas)):
        entrada = _validar(EntradaDeBloco, bruto, f"{nome}[{posicao}]")
        bloco = por_id.get(entrada.bloco)
        if bloco is None or bloco.tipo != declaracao.tipo_bloco:
            raise SlotInvalido(
                f"{nome}[{posicao}]: bloco {entrada.bloco!r} nao e de {declaracao.tipo_bloco}"
            )
        if bloco.id in usados:
            raise SlotInvalido(f"{nome}[{posicao}]: bloco {bloco.id!r} repetido")
        usados.add(bloco.id)
        bullets = _lista(entrada.bullets, f"{nome}[{posicao}].bullets", declaracao.max_bullets)
        saida.append(
            _fatos(bloco, idioma, config)
            | {
                "bullets": [
                    _texto_com_techs(
                        bullet.model_dump(),
                        declaracao.max_chars,
                        permitidas,
                        f"{nome}[{posicao}].bullet",
                    )
                    for bullet in bullets
                ]
            }
        )
    return saida


def contexto_dos_slots(
    slots: dict,
    idioma: str,
    config: ConfiguracaoGerador,
    blocos: Blocos,
    inventario: Inventario,
) -> dict:
    nao_declarados = sorted(set(slots) - set(config.slots))
    if nao_declarados:
        raise SlotNaoDeclarado(f"slot nao declarado: {nao_declarados}")
    ausentes = sorted(set(config.slots) - set(slots))
    if ausentes:
        raise SlotAusente(f"slot ausente: {ausentes}")
    permitidas = frozenset(item.tech for item in inventario.techs)
    contexto: dict = {}
    for nome, declaracao in config.slots.items():
        valor = slots[nome]
        if isinstance(declaracao, SlotTexto):
            contexto[nome] = _texto_com_techs(valor, declaracao.max_chars, permitidas, nome)
        elif isinstance(declaracao, SlotListaTexto):
            itens = [
                texto_limpo(item, declaracao.max_chars, f"{nome}[{posicao}]")
                for posicao, item in enumerate(_lista(valor, nome, declaracao.max_itens))
            ]
            contexto[nome] = LatexSeguro(", ".join(escapar_latex(item) for item in itens))
        else:
            contexto[nome] = _entradas(nome, valor, declaracao, idioma, config, blocos, permitidas)
    return contexto
