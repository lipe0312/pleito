from __future__ import annotations

from collections.abc import Callable

from src.conteudo.modelo import Inventario
from src.validador.analise import Analise, ContextoConteudo, Vaga, analisar
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador
from src.validador.regras_estrutura import (
    validar_cabecalho,
    validar_escapes,
    validar_estrutura,
    validar_idioma,
    validar_preambulo,
)
from src.validador.regras_experiencias import (
    validar_experiencias,
    validar_experiencias_vazias,
    validar_projetos,
)
from src.validador.regras_fidelidade import (
    validar_copia_da_vaga,
    validar_empresa_da_vaga,
    validar_numeros,
    validar_pontuacao,
    validar_senioridade,
)
from src.validador.resultado import Violacao

FuncaoDeRegra = Callable[[Analise, ConfiguracaoValidador], list[Violacao]]

REGRAS: tuple[FuncaoDeRegra, ...] = (
    validar_preambulo,
    validar_cabecalho,
    validar_experiencias,
    validar_experiencias_vazias,
    validar_numeros,
    validar_empresa_da_vaga,
    validar_copia_da_vaga,
    validar_estrutura,
    validar_projetos,
    validar_escapes,
    validar_idioma,
    validar_pontuacao,
    validar_senioridade,
)

__all__ = ["REGRAS", "Analise", "ContextoConteudo", "Vaga", "analisar", "validar_conteudo"]


def validar_conteudo(
    tex: str,
    inventario: Inventario,
    contexto: ContextoConteudo,
    config: ConfiguracaoValidador | None = None,
) -> list[Violacao]:
    config = config or configuracao_validador()
    analise = analisar(tex, inventario, contexto, config)
    violacoes: list[Violacao] = []
    for funcao in REGRAS:
        violacoes += funcao(analise, config)
    return list(dict.fromkeys(violacoes))
