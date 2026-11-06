from __future__ import annotations

from pathlib import Path

from jinja2 import FileSystemLoader, StrictUndefined, meta
from jinja2.sandbox import ImmutableSandboxedEnvironment

from src.config import RAIZ
from src.conteudo.modelo import Blocos, Inventario
from src.gerador.configuracao import ConfiguracaoGerador, configuracao_gerador
from src.gerador.erros import IdiomaNaoSuportado, TemplateInvalido
from src.gerador.escape import LatexSeguro, escapar_latex
from src.gerador.slots import contexto_dos_slots
from src.gerador.travado import Travado, contexto_travado


def _finalizar(valor: object) -> str:
    if isinstance(valor, LatexSeguro):
        return valor
    return LatexSeguro(escapar_latex(str(valor)))


def criar_ambiente(config: ConfiguracaoGerador, pasta: Path | str) -> ImmutableSandboxedEnvironment:
    delimitadores = config.jinja
    return ImmutableSandboxedEnvironment(
        loader=FileSystemLoader(str(pasta)),
        block_start_string=delimitadores.bloco[0],
        block_end_string=delimitadores.bloco[1],
        variable_start_string=delimitadores.variavel[0],
        variable_end_string=delimitadores.variavel[1],
        comment_start_string=delimitadores.comentario[0],
        comment_end_string=delimitadores.comentario[1],
        autoescape=False,
        undefined=StrictUndefined,
        finalize=_finalizar,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _ambiente_dos_templates(config: ConfiguracaoGerador) -> ImmutableSandboxedEnvironment:
    return criar_ambiente(config, RAIZ / config.templates.pasta)


def variaveis_do_template(config: ConfiguracaoGerador, idioma: str) -> set[str]:
    ambiente = _ambiente_dos_templates(config)
    fonte, _, _ = ambiente.loader.get_source(ambiente, config.templates.arquivos[idioma])
    return meta.find_undeclared_variables(ambiente.parse(fonte))


def renderizar(
    idioma: str,
    slots: dict,
    travado: Travado,
    blocos: Blocos,
    inventario: Inventario,
    config: ConfiguracaoGerador | None = None,
) -> str:
    config = config or configuracao_gerador()
    if idioma not in config.templates.arquivos or idioma not in blocos.idiomas:
        raise IdiomaNaoSuportado(f"sem template ou sem blocos para {idioma!r}")
    desconhecidas = (
        variaveis_do_template(config, idioma) - set(config.slots) - set(config.travado.nomes)
    )
    if desconhecidas:
        raise TemplateInvalido(f"template usa variavel nao declarada: {sorted(desconhecidas)}")
    contexto = contexto_dos_slots(slots, idioma, config, blocos, inventario)
    contexto |= contexto_travado(travado, idioma, config)
    ambiente = _ambiente_dos_templates(config)
    return ambiente.get_template(config.templates.arquivos[idioma]).render(**contexto)
