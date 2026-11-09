from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from src.conteudo.modelo import Blocos, Inventario
from src.gerador.compilar import CompilacaoFalhou, PaginasDemais, compilar
from src.gerador.configuracao import (
    ConfiguracaoGerador,
    SlotEntradas,
    SlotTexto,
    configuracao_gerador,
)
from src.gerador.corte import PASSOS, Ajustes, Candidato, ContextoDoCorte, aplicar_ajustes
from src.gerador.erros import RespostaDescartada, SlotInvalido
from src.gerador.escape import texto_limpo
from src.gerador.gerar import ModoGeracao, MotivoSemIa, pedir_slots, versao_do_prompt
from src.gerador.registro import (
    agora,
    gravar_historico,
    gravar_json,
    ler_historico,
    nova_pasta_de_tentativa,
    proxima_tentativa,
    publicar,
    resumo_das_regras,
    violacoes_em_json,
)
from src.gerador.renderizar import renderizar
from src.gerador.retorno import (
    codigo_da_violacao,
    retorno_de_descarte,
    retorno_de_melhoria,
    retorno_de_refacao,
    retorno_de_violacoes,
)
from src.gerador.selecao import slots_sem_ia, techs_da_vaga
from src.gerador.travado import Travado
from src.llm.orcamento import OrcamentoEsgotado
from src.llm.roteador import ModeloIndisponivel, Roteador
from src.padroes.configuracao import ConfiguracaoPadroes, configuracao_padroes
from src.padroes.prompt import montar_prompt
from src.padroes.rubrica import CurriculoAvaliado, avaliar
from src.validador.analise import ContextoConteudo, Vaga
from src.validador.banco import BancoTecnologias
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador
from src.validador.resultado import Regra, Resultado
from src.validador.validar import validar_curriculo, validar_fonte
from src.validador.vocabulario import Vocabulario

RegistrarPendencia = Callable[[str, str, str], None]
Compilador = Callable[[str, Path, ConfiguracaoGerador], Path]


class Estado(StrEnum):
    APROVADO = "aprovado"
    CURRICULO_INVALIDO = "curriculo_invalido"
    ADIADO = "adiado"


class Origem(StrEnum):
    INICIAL = "inicial"
    VIOLACOES = "violacoes"
    DESCARTE = "descarte"
    MELHORIA = "melhoria"
    REFACAO = "refacao"


class ResultadoPasso(StrEnum):
    SEM_EFEITO = "sem_efeito"
    RECUSADO = "recusado"
    AINDA_ESTOURA = "ainda_estoura"
    RESOLVEU = "resolveu"


class RefacaoRecusada(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PedidoDeGeracao:
    familia: str
    idioma: str
    vaga: Vaga
    blocos: Blocos
    inventario: Inventario
    travado: Travado
    banco: BancoTecnologias | None = None
    vocabulario: Vocabulario | None = None

    @property
    def texto_da_vaga(self) -> str:
        return "\n".join(parte for parte in (self.vaga.titulo, self.vaga.descricao) if parte)


@dataclass(frozen=True, slots=True)
class PassoDeCorte:
    passo: int
    nome: str
    resultado: ResultadoPasso
    regras: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Tentativa:
    numero: int
    origem: Origem
    modo: ModoGeracao
    resultado: Resultado | None
    pasta: Path
    slots: dict | None = None
    nota: float | None = None
    fracos: tuple[str, ...] = ()
    corte: tuple[PassoDeCorte, ...] = ()
    descartada: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoDoLaco:
    estado: Estado
    tentativas: tuple[Tentativa, ...]
    escolhida: int | None = None
    melhor: int | None = None
    interrompido: str = ""


@dataclass(slots=True)
class _Geracao:
    modo: ModoGeracao
    slots: dict | None = None
    motivo_sem_ia: MotivoSemIa | None = None
    prompt_versao: str = ""
    prompt_sha256: str = ""
    medida: dict = field(default_factory=dict)
    descartada: str = ""


@contextmanager
def _medindo(roteador: Roteador) -> Iterator[dict]:
    medida: dict = {}
    reservar, finalizar = roteador.reservar, roteador.finalizar

    def reservar_medindo(**dados):
        uso = reservar(**dados)
        medida.update(modelo=dados["modelo"], tier=dados["tier"])
        medida["custo_maximo_usd"] = str(dados["custo_maximo_usd"])
        return uso

    def finalizar_medindo(uso_id, entrada, saida, custo, status):
        medida.update(custo_usd=str(custo), tokens_entrada=entrada, tokens_saida=saida)
        return finalizar(uso_id, entrada, saida, custo, status)

    roteador.reservar, roteador.finalizar = reservar_medindo, finalizar_medindo
    try:
        yield medida
    finally:
        roteador.reservar, roteador.finalizar = reservar, finalizar


class _Laco:
    def __init__(
        self,
        pedido: PedidoDeGeracao,
        pasta: Path,
        roteador: Roteador | None,
        config: ConfiguracaoGerador,
        padroes: ConfiguracaoPadroes,
        validador: ConfiguracaoValidador,
        compilador: Compilador,
        registrar_pendencia: RegistrarPendencia | None,
        motivo: str,
    ) -> None:
        self.pedido = pedido
        self.pasta = pasta
        self.roteador = roteador
        self.config = config
        self.padroes = padroes
        self.validador = validador
        self.compilador = compilador
        self.registrar_pendencia = registrar_pendencia
        self.motivo = motivo
        self.techs_vaga = techs_da_vaga(pedido.texto_da_vaga, pedido.inventario)
        self.contexto = ContextoConteudo(
            blocos=pedido.blocos,
            vaga=pedido.vaga,
            padroes=padroes,
            travado=pedido.travado,
            idioma=pedido.idioma,
            banco=pedido.banco,
            vocabulario=pedido.vocabulario,
        )
        self.contexto_do_corte = ContextoDoCorte(
            idioma=pedido.idioma,
            blocos=pedido.blocos,
            techs_vaga=self.techs_vaga,
            config=config,
            validador=validador,
        )

    def rodar(self) -> ResultadoDoLaco:
        tentativas: list[Tentativa] = []
        origem = Origem.REFACAO if self.motivo else Origem.INICIAL
        retorno = ""
        melhoria_usada = False
        interrompido = ""
        for _ in range(self.config.laco.tentativas_max):
            try:
                geracao = self._gerar(retorno, primeira=not tentativas)
            except (OrcamentoEsgotado, ModeloIndisponivel) as erro:
                interrompido = type(erro).__name__
                break
            tentativa = self._processar(origem, geracao)
            tentativas.append(tentativa)
            if tentativa.modo is ModoGeracao.SEM_IA:
                break
            if tentativa.descartada:
                origem = Origem.DESCARTE
                retorno = retorno_de_descarte(tentativa.descartada, self.config, self.padroes)
                continue
            if not tentativa.resultado.aprovado:
                origem = Origem.VIOLACOES
                retorno = retorno_de_violacoes(
                    tentativa.resultado.bloqueios, self.config, self.padroes
                )
                continue
            if tentativa.nota < self.config.laco.nota_minima and not melhoria_usada:
                melhoria_usada = True
                origem = Origem.MELHORIA
                retorno = retorno_de_melhoria(list(tentativa.fracos), self.config, self.padroes)
                continue
            break
        return self._concluir(tuple(tentativas), interrompido)

    def _prompt(self, retorno: str) -> tuple[int, str]:
        prompt = montar_prompt(
            self.padroes,
            self.pedido.idioma,
            self.pedido.familia,
            self.pedido.texto_da_vaga,
            self.pedido.blocos,
            self.pedido.inventario,
        )
        partes = [prompt.texto]
        if self.motivo:
            partes.append(retorno_de_refacao(self.motivo, self.config, self.padroes))
        if retorno:
            partes.append(retorno)
        return prompt.versao, "\n\n".join(partes)

    def _sem_ia(self, motivo: MotivoSemIa) -> _Geracao:
        slots, _ = slots_sem_ia(
            self.pedido.familia,
            self.pedido.idioma,
            self.pedido.texto_da_vaga,
            self.pedido.blocos,
            self.pedido.inventario,
            self.config,
            self.padroes,
        )
        return _Geracao(modo=ModoGeracao.SEM_IA, slots=slots, motivo_sem_ia=motivo)

    def _gerar(self, retorno: str, primeira: bool) -> _Geracao:
        pode_cair_sem_ia = primeira and not self.motivo
        if self.roteador is None:
            if pode_cair_sem_ia:
                return self._sem_ia(MotivoSemIa.SEM_ROTEADOR)
            raise ModeloIndisponivel("sem roteador")
        versao, texto = self._prompt(retorno)
        versao_completa = versao_do_prompt(versao, texto)
        geracao = _Geracao(modo=ModoGeracao.IA, prompt_versao=versao_completa)
        geracao.prompt_sha256 = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        with _medindo(self.roteador) as medida:
            geracao.medida = medida
            try:
                geracao.slots, _ = pedir_slots(
                    self.roteador,
                    texto,
                    versao_completa,
                    self.pedido.blocos,
                    self.pedido.inventario,
                    self.config,
                )
            except RespostaDescartada as erro:
                geracao.descartada = str(erro) or type(erro).__name__
            except ModeloIndisponivel:
                if not pode_cair_sem_ia:
                    raise
                return self._sem_ia(MotivoSemIa.MODELO_INDISPONIVEL)
            except OrcamentoEsgotado:
                if not pode_cair_sem_ia:
                    raise
                return self._sem_ia(MotivoSemIa.SEM_ORCAMENTO)
        return geracao

    def _montar(self, candidato: Candidato) -> str:
        tex = renderizar(
            self.pedido.idioma,
            candidato.slots,
            self.pedido.travado,
            self.pedido.blocos,
            self.pedido.inventario,
            self.config,
        )
        return aplicar_ajustes(tex, candidato.ajustes, self.config)

    def _fonte(self, tex: str) -> Resultado:
        return validar_fonte(tex, self.pedido.inventario, self.validador, banco=self.pedido.banco)

    def _compilado(self, tex: str, pasta: Path) -> tuple[Resultado, bool]:
        nome = self.config.compilacao.nome_arquivo
        try:
            pdf: Path | None = self.compilador(tex, pasta, self.config)
        except PaginasDemais:
            pdf = pasta / f"{nome}.pdf"
        except CompilacaoFalhou:
            pdf = None
        resultado = validar_curriculo(
            tex,
            self.pedido.inventario,
            self.validador,
            pdf,
            contexto=self.contexto,
            log=pasta / f"{nome}.log",
        )
        estourou = pdf is not None and Regra.PAGINAS in resultado.regras_bloqueadas
        return resultado, estourou

    def _cortar(
        self, candidato: Candidato, tex: str, resultado: Resultado, pasta: Path
    ) -> tuple[Candidato, str, Resultado, tuple[PassoDeCorte, ...]]:
        passos: list[PassoDeCorte] = []
        for indice, nome in enumerate(self.config.corte.ordem, 1):
            novo = PASSOS[nome](candidato, self.contexto_do_corte)
            tex_novo = self._montar(novo) if novo is not None else tex
            if novo is None or tex_novo == tex:
                passos.append(PassoDeCorte(indice, nome, ResultadoPasso.SEM_EFEITO))
                continue
            fonte = self._fonte(tex_novo)
            if not fonte.aprovado:
                codigos = tuple(dict.fromkeys(codigo_da_violacao(v) for v in fonte.bloqueios))
                passos.append(PassoDeCorte(indice, nome, ResultadoPasso.RECUSADO, codigos))
                continue
            candidato, tex = novo, tex_novo
            resultado, estourou = self._compilado(tex, pasta)
            situacao = ResultadoPasso.AINDA_ESTOURA if estourou else ResultadoPasso.RESOLVEU
            passos.append(PassoDeCorte(indice, nome, situacao))
            if not estourou:
                break
        return candidato, tex, resultado, tuple(passos)

    def _nota(self, slots: dict) -> tuple[float, tuple[str, ...]]:
        sobre = next(n for n, d in self.config.slots.items() if isinstance(d, SlotTexto))
        bullets = [
            entrada["bullets"]
            for nome, declaracao in self.config.slots.items()
            if isinstance(declaracao, SlotEntradas)
            for entrada in slots[nome]
        ]
        curriculo = CurriculoAvaliado.model_validate(
            {"sobre": slots[sobre], "bullets_por_entrada": bullets}
        )
        nota = avaliar(
            self.padroes,
            curriculo,
            self.pedido.idioma,
            self.pedido.familia,
            sorted(self.techs_vaga),
            [item.tech for item in self.pedido.inventario.techs],
        )
        fracos = tuple(nome for nome, valor in nota.notas.items() if valor < 1)
        return nota.total, fracos

    def _processar(self, origem: Origem, geracao: _Geracao) -> Tentativa:
        numero = proxima_tentativa(self.pasta, self.config)
        pasta = nova_pasta_de_tentativa(self.pasta, numero, self.config)
        tentativa = Tentativa(
            numero, origem, geracao.modo, None, pasta, descartada=geracao.descartada
        )
        if not geracao.descartada:
            tentativa = self._avaliar(tentativa, Candidato(geracao.slots, Ajustes()))
        self._gravar(tentativa, geracao)
        return tentativa

    def _avaliar(self, tentativa: Tentativa, candidato: Candidato) -> Tentativa:
        try:
            tex = self._montar(candidato)
        except SlotInvalido as erro:
            return _com(tentativa, descartada=str(erro), slots=candidato.slots)
        nome = self.config.compilacao.nome_arquivo
        (tentativa.pasta / f"{nome}.tex").write_text(tex, encoding="utf-8")
        resultado = self._fonte(tex)
        corte: tuple[PassoDeCorte, ...] = ()
        if resultado.aprovado:
            resultado, estourou = self._compilado(tex, tentativa.pasta)
            if estourou:
                candidato, tex, resultado, corte = self._cortar(
                    candidato, tex, resultado, tentativa.pasta
                )
            (tentativa.pasta / f"{nome}.tex").write_text(tex, encoding="utf-8")
        nota, fracos = self._nota(candidato.slots) if resultado.aprovado else (None, ())
        return _com(
            tentativa,
            resultado=resultado,
            slots=candidato.slots,
            nota=nota,
            fracos=fracos,
            corte=corte,
        )

    def _gravar(self, tentativa: Tentativa, geracao: _Geracao) -> None:
        arquivos = self.config.laco.arquivos
        gravar_json(tentativa.pasta / arquivos.slots, tentativa.slots)
        gravar_json(tentativa.pasta / arquivos.validacao, violacoes_em_json(tentativa.resultado))
        medida = geracao.medida
        gravar_json(
            tentativa.pasta / arquivos.meta,
            {
                "tentativa": tentativa.numero,
                "origem": str(tentativa.origem),
                "modo": str(tentativa.modo),
                "motivo_sem_ia": str(geracao.motivo_sem_ia) if geracao.motivo_sem_ia else None,
                "motivo": self.motivo or None,
                "familia": self.pedido.familia,
                "idioma": self.pedido.idioma,
                "modelo": medida.get("modelo"),
                "tier": medida.get("tier"),
                "prompt_versao": geracao.prompt_versao or None,
                "prompt_sha256": geracao.prompt_sha256 or None,
                "custo_usd": medida.get("custo_usd", "0"),
                "custo_maximo_usd": medida.get("custo_maximo_usd"),
                "tokens_entrada": medida.get("tokens_entrada"),
                "tokens_saida": medida.get("tokens_saida"),
                "descartada": tentativa.descartada or None,
                "corte": [
                    {
                        "passo": passo.passo,
                        "nome": passo.nome,
                        "resultado": str(passo.resultado),
                        "regras": list(passo.regras),
                    }
                    for passo in tentativa.corte
                ],
                "regras": resumo_das_regras(tentativa.resultado),
                "nota": tentativa.nota,
                "fracos": list(tentativa.fracos),
                "criada_em": agora(),
            },
        )

    def _concluir(self, tentativas: tuple[Tentativa, ...], interrompido: str) -> ResultadoDoLaco:
        aprovadas = [t for t in tentativas if t.resultado is not None and t.resultado.aprovado]
        if aprovadas:
            escolhida = max(aprovadas, key=lambda t: (t.nota or 0, -t.numero))
            publicar(
                self.pasta,
                escolhida.pasta,
                escolhida.numero,
                {
                    "familia": self.pedido.familia,
                    "idioma": self.pedido.idioma,
                    "motivo": self.motivo or None,
                },
                self.config,
            )
            return ResultadoDoLaco(
                Estado.APROVADO, tentativas, escolhida.numero, escolhida.numero, interrompido
            )
        melhor = min(
            tentativas,
            key=lambda t: (len(t.resultado.bloqueios) if t.resultado else float("inf"), t.numero),
            default=None,
        )
        numero = melhor.numero if melhor else None
        if interrompido:
            return ResultadoDoLaco(Estado.ADIADO, tentativas, None, numero, interrompido)
        if self.registrar_pendencia is not None:
            self.registrar_pendencia(*self._pendencia(tentativas, melhor))
        return ResultadoDoLaco(Estado.CURRICULO_INVALIDO, tentativas, None, numero)

    def _pendencia(
        self, tentativas: tuple[Tentativa, ...], melhor: Tentativa | None
    ) -> tuple[str, str, str]:
        codigos = []
        if melhor is not None and melhor.resultado is not None:
            codigos = list(dict.fromkeys(codigo_da_violacao(v) for v in melhor.resultado.bloqueios))
        elif melhor is not None:
            codigos = [Origem.DESCARTE.value]
        detalhe = f"{len(tentativas)} tentativas; violacoes da melhor: {', '.join(codigos)}"
        link = f"{self.config.laco.pasta_tentativas}/{melhor.numero}" if melhor is not None else ""
        return self.config.laco.categoria_pendencia, detalhe, link


def _com(tentativa: Tentativa, **campos) -> Tentativa:
    return replace(tentativa, **campos)


def executar_laco(
    pedido: PedidoDeGeracao,
    pasta: Path,
    roteador: Roteador | None,
    *,
    motivo: str = "",
    config: ConfiguracaoGerador | None = None,
    padroes: ConfiguracaoPadroes | None = None,
    validador: ConfiguracaoValidador | None = None,
    compilador: Compilador = compilar,
    registrar_pendencia: RegistrarPendencia | None = None,
) -> ResultadoDoLaco:
    return _Laco(
        pedido,
        pasta,
        roteador,
        config or configuracao_gerador(),
        padroes or configuracao_padroes(),
        validador or configuracao_validador(),
        compilador,
        registrar_pendencia,
        motivo,
    ).rodar()


def refazer(
    pedido: PedidoDeGeracao,
    pasta: Path,
    roteador: Roteador | None,
    motivo: str,
    *,
    config: ConfiguracaoGerador | None = None,
    padroes: ConfiguracaoPadroes | None = None,
    validador: ConfiguracaoValidador | None = None,
    compilador: Compilador = compilar,
    registrar_pendencia: RegistrarPendencia | None = None,
) -> ResultadoDoLaco:
    config = config or configuracao_gerador()
    historico = ler_historico(pasta, config)
    if not historico["versoes"]:
        raise RefacaoRecusada("sem versao anterior para refazer")
    if len(historico["refacoes"]) >= config.laco.refacoes_max:
        raise RefacaoRecusada(f"limite de {config.laco.refacoes_max} refacoes atingido")
    try:
        limpo = texto_limpo(motivo, config.laco.motivo_max_chars, "motivo")
    except SlotInvalido as erro:
        raise RefacaoRecusada(str(erro)) from erro
    pedida = {"motivo": limpo, "pedida_em": agora()}
    historico["refacoes"].append(pedida)
    gravar_historico(pasta, historico, config)
    resultado = executar_laco(
        pedido,
        pasta,
        roteador,
        motivo=limpo,
        config=config,
        padroes=padroes,
        validador=validador,
        compilador=compilador,
        registrar_pendencia=registrar_pendencia,
    )
    if resultado.estado is Estado.ADIADO and not resultado.tentativas:
        historico = ler_historico(pasta, config)
        historico["refacoes"] = [r for r in historico["refacoes"] if r != pedida]
        gravar_historico(pasta, historico, config)
    return resultado
