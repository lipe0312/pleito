from __future__ import annotations

import re
import unicodedata

from src.conteudo.decompor import ESCAPE, TECH
from src.conteudo.modelo import Inventario
from src.validador.banco import BancoTecnologias, Evidencia, forca_da_evidencia
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.latex import corpo_do_tex
from src.validador.resultado import Nivel, Regra, Violacao
from src.validador.texto import ao_redor, palavras
from src.validador.vocabulario import TermosDoIdioma

MARCADOR = re.compile(r"\\tech(?![A-Za-z])")
DESTINO_DO_LINK = re.compile(r"\\href\s*\{[^{}]*\}")
COMANDO_COM_LETRAS = re.compile(r"\\[A-Za-z]+")
SIMBOLO_DE_CONTROLE = re.compile(r"\\[^A-Za-z]", re.S)
ESPACOS = re.compile(r"\s+")


EVIDENCIAS_MOSTRADAS = 3


def _violacao(detalhe: str) -> Violacao:
    return Violacao(Regra.TECNOLOGIA, detalhe)


def _palavra(nome: str, exigir_caixa: bool = False) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(nome)}(?!\w)", 0 if exigir_caixa else re.IGNORECASE)


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKC", texto)


def _nomes_do_inventario(inventario: Inventario) -> list[str]:
    return sorted({_normalizar(item.tech) for item in inventario.techs}, key=len, reverse=True)


def _descrever(evidencias: list[Evidencia]) -> str:
    return "; ".join(
        f"{e.origem} em {e.ref} ({e.fonte})" for e in evidencias[:EVIDENCIAS_MOSTRADAS]
    )


def _conhecidas(inventario: Inventario, config: ConfiguracaoValidador) -> dict[str, str]:
    nomes = [*config.tecnologias_conhecidas, *config.dicionario_tecnologias]
    nomes += [equivalencia.pedido for equivalencia in inventario.equivalencias]
    return {_normalizar(nome).casefold(): _normalizar(nome) for nome in nomes}


def _classificar(
    nome: str,
    trecho: str,
    evidencias: list[Evidencia],
    banco: BancoTecnologias | None,
    config: ConfiguracaoValidador,
) -> Violacao:
    fortes = [e for e in evidencias if forca_da_evidencia(e, config) == "forte"]
    if fortes:
        return Violacao(
            Regra.TECNOLOGIA,
            f"tecnologia citada com evidencia no banco: {nome}",
            trecho,
            "",
            Nivel.OK,
            f"salvou: {_descrever(fortes)}",
        )
    if evidencias:
        return Violacao(
            Regra.TECNOLOGIA,
            f"tecnologia citada com evidencia fraca: {nome}",
            trecho,
            f"confirme {nome} nos projetos ou tire do texto antes de enviar",
            Nivel.INDICIO,
            f"faltou evidencia forte; so ha: {_descrever(evidencias)}",
        )
    faltou = "nenhuma evidencia no banco de tecnologias"
    if banco is None:
        faltou = "banco de tecnologias ausente, rode make validador-dados"
    return Violacao(
        Regra.TECNOLOGIA,
        f"tecnologia fora do inventario: {nome}",
        trecho,
        f"tire {nome} ou cite so tecnologia do inventario, com \\tech{{}}",
        Nivel.BLOQUEIA,
        f"faltou: {faltou}",
    )


def _coberta_pelo_vocabulario(inicio: int, fim: int, formas: list, cobertas: set[int]) -> bool:
    indices = [i for i, p in enumerate(formas) if p.inicio < fim and p.fim > inicio]
    return bool(indices) and all(i in cobertas for i in indices)


def validar_tecnologias_no_texto(
    texto: str,
    inventario: Inventario,
    config: ConfiguracaoValidador,
    banco: BancoTecnologias | None = None,
    vocabulario: TermosDoIdioma | None = None,
) -> list[Violacao]:
    restante = ESPACOS.sub(" ", _normalizar(texto))
    for nome in _nomes_do_inventario(inventario):
        restante = _palavra(nome).sub(" ", restante)
    pedidos = {_normalizar(e.pedido).casefold() for e in inventario.equivalencias}
    caixa = {_normalizar(nome) for nome in config.tecnologias.exigir_caixa}
    formas = palavras(restante)
    cobertas = vocabulario.cobertura(formas) if vocabulario else set()
    achadas = []
    for chave, nome in _conhecidas(inventario, config).items():
        achado = _palavra(nome, nome in caixa).search(restante)
        if achado:
            achadas.append((nome, chave, achado))
    violacoes = []
    for nome, chave, achado in sorted(achadas, key=lambda item: item[0]):
        if any(
            outro.start() <= achado.start()
            and achado.end() <= outro.end()
            and outro is not achado
            and (outro.end() - outro.start()) > (achado.end() - achado.start())
            for _, _, outro in achadas
        ):
            continue
        trecho = ao_redor(restante, achado.start(), achado.end(), config)
        if chave not in pedidos and _coberta_pelo_vocabulario(
            achado.start(), achado.end(), formas, cobertas
        ):
            violacoes.append(
                Violacao(
                    Regra.TECNOLOGIA,
                    f"tecnologia dentro de termo do vocabulario do curriculo: {nome}",
                    trecho,
                    "",
                    Nivel.OK,
                    "salvou: vocabulario do curriculo cobre o termo",
                )
            )
            continue
        evidencias = banco.evidencias_de(nome) if banco else []
        violacoes.append(_classificar(nome, trecho, evidencias, banco, config))
    return violacoes


def _texto_visivel(corpo: str) -> str:
    sem_link = DESTINO_DO_LINK.sub(" ", TECH.sub(" ", corpo))
    desescapado = ESCAPE.sub(r"\1", sem_link)
    sem_simbolos = SIMBOLO_DE_CONTROLE.sub(" ", desescapado)
    return COMANDO_COM_LETRAS.sub("", sem_simbolos).replace("{", "").replace("}", "")


def validar_tecnologias(
    tex: str,
    inventario: Inventario,
    config: ConfiguracaoValidador,
    banco: BancoTecnologias | None = None,
    vocabulario: TermosDoIdioma | None = None,
) -> list[Violacao]:
    corpo = corpo_do_tex(tex, config)
    permitidas = {_normalizar(item.tech).casefold() for item in inventario.techs}
    marcadas = [_normalizar(ESCAPE.sub(r"\1", nome)).strip() for nome in TECH.findall(corpo)]
    violacoes = []
    if len(MARCADOR.findall(corpo)) != len(marcadas):
        violacoes.append(_violacao("marcador tech malformado"))
    violacoes += [
        _violacao(f"tecnologia fora do inventario: {nome}")
        for nome in dict.fromkeys(marcadas)
        if nome.casefold() not in permitidas
    ]
    violacoes += validar_tecnologias_no_texto(
        _texto_visivel(corpo), inventario, config, banco, vocabulario
    )
    return violacoes
