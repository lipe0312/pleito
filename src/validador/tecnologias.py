from __future__ import annotations

import re
import unicodedata

from src.conteudo.decompor import ESCAPE, TECH
from src.conteudo.modelo import Inventario
from src.validador.banco import BancoTecnologias, Evidencia, forca_da_evidencia
from src.validador.configuracao import ConfiguracaoValidador
from src.validador.latex import corpo_do_tex
from src.validador.resultado import Nivel, Regra, Violacao
from src.validador.texto import ao_redor

MARCADOR = re.compile(r"\\tech(?![A-Za-z])")
DESTINO_DO_LINK = re.compile(r"\\href\s*\{[^{}]*\}")
COMANDO_COM_LETRAS = re.compile(r"\\[A-Za-z]+")
SIMBOLO_DE_CONTROLE = re.compile(r"\\[^A-Za-z]", re.S)
ESPACOS = re.compile(r"\s+")


def _violacao(detalhe: str) -> Violacao:
    return Violacao(Regra.TECNOLOGIA, detalhe)


def _palavra(nome: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(nome)}(?!\w)", re.IGNORECASE)


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKC", texto)


def _nomes_do_inventario(inventario: Inventario) -> list[str]:
    return sorted({_normalizar(item.tech) for item in inventario.techs}, key=len, reverse=True)


def _descrever(evidencias: list[Evidencia], config: ConfiguracaoValidador) -> str:
    return "; ".join(
        f"{e.origem} em {e.ref} ({e.fonte})"
        for e in evidencias[: config.tecnologias.evidencias_mostradas]
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
            f"salvou: {_descrever(fortes, config)}",
        )
    if evidencias:
        return Violacao(
            Regra.TECNOLOGIA,
            f"tecnologia citada com evidencia fraca: {nome}",
            trecho,
            f"confirme {nome} nos projetos ou tire do texto antes de enviar",
            Nivel.INDICIO,
            f"faltou evidencia forte; so ha: {_descrever(evidencias, config)}",
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


def _palavra_comum_em_outra_caixa(nome: str, trecho: str) -> Violacao:
    return Violacao(
        Regra.TECNOLOGIA,
        f"nome de tecnologia que tambem e palavra comum, fora da caixa do dicionario: {nome}",
        trecho,
        f"se for a tecnologia {nome}, cite pelo inventario com \\tech{{}}; se nao, ignore",
        Nivel.INDICIO,
        f"faltou: caixa exata do dicionario; {nome} tambem e palavra comum",
    )


def validar_tecnologias_no_texto(
    texto: str,
    inventario: Inventario,
    config: ConfiguracaoValidador,
    banco: BancoTecnologias | None = None,
) -> list[Violacao]:
    restante = ESPACOS.sub(" ", _normalizar(texto))
    for nome in _nomes_do_inventario(inventario):
        restante = _palavra(nome).sub(" ", restante)
    comuns = {_normalizar(nome) for nome in config.tecnologias.palavras_comuns}
    achadas = []
    for nome in _conhecidas(inventario, config).values():
        ocorrencias = list(_palavra(nome).finditer(restante))
        if not ocorrencias:
            continue
        exatas = [o for o in ocorrencias if o.group(0) == nome]
        if nome in comuns and not exatas:
            achadas.append((nome, ocorrencias[0], False))
        else:
            achadas.append((nome, (exatas or ocorrencias)[0], True))
    violacoes = []
    for nome, achado, tecnologia in sorted(achadas, key=lambda item: item[0]):
        if any(
            outro.start() <= achado.start()
            and achado.end() <= outro.end()
            and (outro.end() - outro.start()) > (achado.end() - achado.start())
            for _, outro, _ in achadas
        ):
            continue
        trecho = ao_redor(restante, achado.start(), achado.end(), config)
        if not tecnologia:
            violacoes.append(_palavra_comum_em_outra_caixa(nome, trecho))
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
    violacoes += validar_tecnologias_no_texto(_texto_visivel(corpo), inventario, config, banco)
    return violacoes
