from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.avaliacao.conjunto import Conteudo, Entrada
from src.gerador.configuracao import configuracao_gerador
from src.gerador.erros import RespostaDescartada
from src.gerador.gerar import ModoGeracao, gerar_curriculo
from src.llm.roteador import Roteador
from src.padroes.configuracao import configuracao_padroes
from src.padroes.prompt import montar_prompt
from src.validador.analise import ContextoConteudo, Vaga
from src.validador.conteudo import validar_conteudo
from src.validador.resultado import CurriculoInvalido, Nivel

FALHA_ESQUEMA = "esquema"
FALHA_PROIBIDO = "proibido"
PREFIXO_SEM_IA = "sem_ia_"


@dataclass(frozen=True, slots=True)
class Execucao:
    entrada: Entrada
    caso: str
    versao_prompt: str
    falhas: tuple[str, ...]

    @property
    def aprovada(self) -> bool:
        return not self.falhas


Executor = Callable[[Entrada, Conteudo, Roteador, str, str, str], Execucao]


def _textos(valor: object) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [texto for item in valor.values() for texto in _textos(item)]
    if isinstance(valor, list | tuple):
        return [texto for item in valor for texto in _textos(item)]
    return []


def termos_proibidos(slots: object, proibidos: list[str]) -> list[str]:
    texto = "\n".join(_textos(slots)).casefold()
    return [termo for termo in proibidos if termo.casefold() in texto]


def gerar_e_validar(
    entrada: Entrada, conteudo: Conteudo, roteador: Roteador, caso: str, tarefa: str, tier: str
) -> Execucao:
    gerador = configuracao_gerador()
    gerador = gerador.model_copy(
        update={"ia": gerador.ia.model_copy(update={"tarefa": tarefa, "tier": tier})}
    )
    padroes = configuracao_padroes()
    prompt = montar_prompt(
        padroes,
        entrada.idioma,
        entrada.familia,
        entrada.texto,
        conteudo.blocos,
        conteudo.inventario,
    )
    versao = f"{Path(padroes.prompt.arquivo).stem}_v{prompt.versao}"

    def execucao(*falhas: str) -> Execucao:
        return Execucao(entrada, caso, versao, tuple(dict.fromkeys(falhas)))

    try:
        resultado = gerar_curriculo(
            entrada.familia,
            entrada.idioma,
            entrada.texto,
            conteudo.blocos,
            conteudo.inventario,
            conteudo.travado,
            roteador,
            gerador,
            padroes,
        )
    except CurriculoInvalido as erro:
        return execucao(*(regra.value for regra in erro.resultado.regras_bloqueadas))
    except RespostaDescartada:
        return execucao(FALHA_ESQUEMA)
    if resultado.modo is not ModoGeracao.IA:
        return execucao(f"{PREFIXO_SEM_IA}{resultado.motivo}")
    contexto = ContextoConteudo(
        blocos=conteudo.blocos,
        vaga=Vaga(empresa=entrada.empresa, descricao=entrada.texto, titulo=entrada.titulo),
        padroes=padroes,
        travado=conteudo.travado,
        idioma=entrada.idioma,
    )
    falhas = [
        violacao.regra.value
        for violacao in validar_conteudo(resultado.tex, conteudo.inventario, contexto)
        if violacao.nivel is Nivel.BLOQUEIA
    ]
    if termos_proibidos(resultado.slots, entrada.proibidos):
        falhas.append(FALHA_PROIBIDO)
    return execucao(*falhas)


EXECUTORES: dict[str, Executor] = {"gerar_e_validar": gerar_e_validar}
