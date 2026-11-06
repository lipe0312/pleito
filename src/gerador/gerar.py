from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.conteudo.modelo import Blocos, Inventario
from src.gerador.configuracao import ConfiguracaoGerador, configuracao_gerador
from src.gerador.erros import RespostaDescartada, SlotInvalido
from src.gerador.esquema import esquema_dos_slots
from src.gerador.renderizar import renderizar
from src.gerador.resposta import Enfase, slots_da_resposta
from src.gerador.selecao import slots_sem_ia
from src.gerador.travado import Travado
from src.llm.orcamento import OrcamentoEsgotado
from src.llm.roteador import ModeloIndisponivel, Roteador
from src.padroes.configuracao import ConfiguracaoPadroes, configuracao_padroes
from src.padroes.prompt import montar_prompt
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.validar import exigir_fonte_valida


class ModoGeracao(StrEnum):
    IA = "ia"
    SEM_IA = "sem_ia"


class MotivoSemIa(StrEnum):
    MODELO_INDISPONIVEL = "modelo_indisponivel"
    SEM_ORCAMENTO = "sem_orcamento"
    SEM_ROTEADOR = "sem_roteador"


@dataclass(frozen=True, slots=True)
class ResultadoGeracao:
    tex: str
    slots: dict
    enfase: Enfase
    modo: ModoGeracao
    motivo: MotivoSemIa | None = None
    prompt_versao: int | None = None
    prompt_sha256: str | None = None


def _validado(
    idioma: str,
    slots: dict,
    blocos: Blocos,
    inventario: Inventario,
    travado: Travado,
    config: ConfiguracaoGerador,
    validador: ConfiguracaoValidador | None,
) -> str:
    tex = renderizar(idioma, slots, travado, blocos, inventario, config)
    exigir_fonte_valida(tex, inventario, validador)
    return tex


def gerar_sem_ia(
    familia: str,
    idioma: str,
    vaga: str,
    blocos: Blocos,
    inventario: Inventario,
    travado: Travado,
    config: ConfiguracaoGerador | None = None,
    padroes: ConfiguracaoPadroes | None = None,
    validador: ConfiguracaoValidador | None = None,
    motivo: MotivoSemIa | None = None,
) -> ResultadoGeracao:
    config = config or configuracao_gerador()
    padroes = padroes or configuracao_padroes()
    slots, enfase = slots_sem_ia(familia, idioma, vaga, blocos, inventario, config, padroes)
    tex = _validado(idioma, slots, blocos, inventario, travado, config, validador)
    return ResultadoGeracao(
        tex=tex, slots=slots, enfase=enfase, modo=ModoGeracao.SEM_IA, motivo=motivo
    )


def gerar_curriculo(
    familia: str,
    idioma: str,
    vaga: str,
    blocos: Blocos,
    inventario: Inventario,
    travado: Travado,
    roteador: Roteador | None,
    config: ConfiguracaoGerador | None = None,
    padroes: ConfiguracaoPadroes | None = None,
    validador: ConfiguracaoValidador | None = None,
) -> ResultadoGeracao:
    config = config or configuracao_gerador()
    padroes = padroes or configuracao_padroes()

    def sem_ia(motivo: MotivoSemIa) -> ResultadoGeracao:
        return gerar_sem_ia(
            familia, idioma, vaga, blocos, inventario, travado, config, padroes, validador, motivo
        )

    if roteador is None:
        return sem_ia(MotivoSemIa.SEM_ROTEADOR)
    prompt = montar_prompt(padroes, idioma, familia, vaga, blocos, inventario)
    esquema = esquema_dos_slots(config)
    versao = f"gerar_slots_v{prompt.versao}_{prompt.sha256[:12]}"
    try:
        resposta = roteador.chamar(config.ia.tarefa, config.ia.tier, prompt.texto, esquema, versao)
    except ModeloIndisponivel:
        return sem_ia(MotivoSemIa.MODELO_INDISPONIVEL)
    except OrcamentoEsgotado:
        return sem_ia(MotivoSemIa.SEM_ORCAMENTO)
    except ValueError as erro:
        raise RespostaDescartada(f"resposta recusada: {type(erro).__name__}") from erro
    try:
        slots, enfase = slots_da_resposta(resposta, blocos, inventario, config)
        tex = _validado(idioma, slots, blocos, inventario, travado, config, validador)
    except SlotInvalido as erro:
        raise RespostaDescartada(str(erro)) from erro
    return ResultadoGeracao(
        tex=tex,
        slots=slots,
        enfase=enfase,
        modo=ModoGeracao.IA,
        prompt_versao=prompt.versao,
        prompt_sha256=prompt.sha256,
    )
