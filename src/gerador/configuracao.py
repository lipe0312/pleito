from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from src.config import carregar
from src.conteudo.modelo import Estrito, Identificador, TipoAncora, TipoBloco


class Templates(Estrito):
    pasta: str
    arquivos: dict[Identificador, str] = Field(min_length=1)

    @model_validator(mode="after")
    def _arquivos_sem_caminho(self) -> Templates:
        if any(Path(nome).name != nome for nome in self.arquivos.values()):
            raise ValueError("arquivo de template nao pode ter caminho")
        return self


class Delimitadores(Estrito):
    bloco: tuple[str, str]
    variavel: tuple[str, str]
    comentario: tuple[str, str]


class ConfiguracaoTravado(Estrito):
    arquivo: str
    nomes: list[Identificador]
    texto_max_chars: int = Field(gt=0)
    padrao_email: str
    padrao_url: str
    prefixo_url_oculto: str
    campos_url: list[Identificador]

    @model_validator(mode="after")
    def _arquivo_sem_caminho(self) -> ConfiguracaoTravado:
        if Path(self.arquivo).name != self.arquivo:
            raise ValueError("arquivo do travado nao pode ter caminho")
        return self


class SlotTexto(Estrito):
    tipo: Literal["texto"]
    tipo_bloco: TipoBloco
    max_chars: int = Field(gt=0)


class SlotListaTexto(Estrito):
    tipo: Literal["lista_texto"]
    tipo_ancora: TipoAncora
    max_itens: int = Field(gt=0)
    max_chars: int = Field(gt=0)


class SlotEntradas(Estrito):
    tipo: Literal["entradas"]
    tipo_bloco: TipoBloco
    max_entradas: int = Field(gt=0)
    max_bullets: int = Field(gt=0)
    max_chars: int = Field(gt=0)


DeclaracaoSlot = Annotated[SlotTexto | SlotListaTexto | SlotEntradas, Field(discriminator="tipo")]


TRAVAS_DO_MOTOR = {"openin_any": "p", "openout_any": "p", "shell_escape": "f"}


class Compilacao(Estrito):
    motor: str
    nome_arquivo: Identificador
    argumentos: list[str]
    ambiente: dict[str, str]
    variaveis_herdadas: list[str]
    linhas_do_erro: int = Field(gt=0)
    timeout_s: int = Field(gt=0)
    paginas_max: int = Field(gt=0)

    @model_validator(mode="after")
    def _travas_do_motor(self) -> Compilacao:
        if "-no-shell-escape" not in self.argumentos:
            raise ValueError("compilacao exige -no-shell-escape")
        frouxas = {
            chave: self.ambiente.get(chave)
            for chave, valor in TRAVAS_DO_MOTOR.items()
            if self.ambiente.get(chave) != valor
        }
        if frouxas:
            raise ValueError(f"ambiente do motor precisa de {TRAVAS_DO_MOTOR}, achou {frouxas}")
        if set(self.ambiente) & set(self.variaveis_herdadas):
            raise ValueError("variavel herdada nao pode ser fixada no ambiente")
        return self


class ConfiguracaoIa(Estrito):
    tarefa: Identificador
    tier: Identificador
    tipos_na_ordem_dos_blocos: list[TipoBloco]
    tipos_com_enfase: list[TipoBloco]
    entradas_min: dict[TipoBloco, int]
    bullets_min: int = Field(gt=0)
    techs_max: int = Field(gt=0)
    tech_max_chars: int = Field(gt=0)
    enfase_max: int = Field(gt=0)


class ConfiguracaoSemIa(Estrito):
    entradas_por_tipo: dict[TipoBloco, int]
    bullets_por_tipo: dict[TipoBloco, int]
    peso_familia: int = Field(ge=0)
    peso_tech: int = Field(ge=0)


PASSOS_DE_CORTE = (
    "remover_quarto_projeto",
    "encurtar_bullets",
    "reduzir_espaco_vertical",
    "remover_bullet_menos_aderente",
    "reduzir_entrelinha",
    "reduzir_margem_vertical",
)

MEDIDA_EM_MM = r"^[0-9]+(\.[0-9]+)?mm$"


class ArquivosDoLaco(Estrito):
    slots: str
    validacao: str
    meta: str
    diff: str
    historico: str

    @model_validator(mode="after")
    def _sem_caminho(self) -> ArquivosDoLaco:
        nomes = list(self.model_dump().values())
        if any(Path(nome).name != nome for nome in nomes) or len(set(nomes)) != len(nomes):
            raise ValueError("arquivo do laco nao pode ter caminho nem nome repetido")
        return self


class Retorno(Estrito):
    trecho_max_chars: int = Field(gt=0)
    violacoes_max: int = Field(gt=0)
    violacoes: str = Field(min_length=1)
    melhoria: str = Field(min_length=1)
    refacao: str = Field(min_length=1)
    descartada: str = Field(min_length=1)
    regras: dict[str, str] = Field(min_length=1)


class ConfiguracaoLaco(Estrito):
    tentativas_max: int = Field(gt=0)
    nota_minima: float = Field(ge=0, le=1)
    refacoes_max: int = Field(ge=0)
    motivo_max_chars: int = Field(gt=0)
    pasta_vagas: Identificador
    pasta_tentativas: Identificador
    categoria_pendencia: Identificador
    arquivos: ArquivosDoLaco
    retorno: Retorno


class EspacoVertical(Estrito):
    de: str = Field(pattern=MEDIDA_EM_MM)
    para: str = Field(pattern=MEDIDA_EM_MM)


class ConfiguracaoCorte(Estrito):
    ordem: list[Literal[PASSOS_DE_CORTE]] = Field(min_length=1)
    bullet_longo_chars: int = Field(gt=0)
    espaco_vertical: EspacoVertical
    margem_vertical_cm: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordem_sem_repeticao(self) -> ConfiguracaoCorte:
        if len(set(self.ordem)) != len(self.ordem):
            raise ValueError("passo de corte repetido")
        return self


class ConfiguracaoGerador(Estrito):
    templates: Templates
    jinja: Delimitadores
    travado: ConfiguracaoTravado
    slots: dict[Identificador, DeclaracaoSlot] = Field(min_length=1)
    ia: ConfiguracaoIa
    sem_ia: ConfiguracaoSemIa
    compilacao: Compilacao
    laco: ConfiguracaoLaco
    corte: ConfiguracaoCorte

    @model_validator(mode="after")
    def _slot_nao_usa_nome_do_travado(self) -> ConfiguracaoGerador:
        if set(self.slots) & set(self.travado.nomes):
            raise ValueError("slot com o mesmo nome de um dado travado")
        return self

    def entradas_do_tipo(self, tipo: str) -> SlotEntradas:
        achados = [
            declaracao
            for declaracao in self.slots.values()
            if isinstance(declaracao, SlotEntradas) and declaracao.tipo_bloco == tipo
        ]
        if len(achados) != 1:
            raise ValueError(f"precisa de exatamente um slot de entradas do tipo {tipo}")
        return achados[0]

    @model_validator(mode="after")
    def _ia_e_sem_ia_cabem_nos_slots(self) -> ConfiguracaoGerador:
        for tipo in {*self.ia.tipos_na_ordem_dos_blocos, *self.ia.tipos_com_enfase}:
            self.entradas_do_tipo(tipo)
        for tipo, minimo in self.ia.entradas_min.items():
            if not 0 < minimo <= self.entradas_do_tipo(tipo).max_entradas:
                raise ValueError(f"entradas_min de {tipo} fora de 1..max_entradas")
        for tipo, total in self.sem_ia.entradas_por_tipo.items():
            piso = self.ia.entradas_min.get(tipo, 1)
            if not piso <= total <= self.entradas_do_tipo(tipo).max_entradas:
                raise ValueError(f"sem_ia.entradas_por_tipo de {tipo} fora de min..max_entradas")
        for tipo, total in self.sem_ia.bullets_por_tipo.items():
            if not self.ia.bullets_min <= total <= self.entradas_do_tipo(tipo).max_bullets:
                raise ValueError(f"sem_ia.bullets_por_tipo de {tipo} fora de min..max_bullets")
        for declaracao in self.slots.values():
            if isinstance(declaracao, SlotEntradas):
                if declaracao.tipo_bloco not in self.sem_ia.bullets_por_tipo:
                    raise ValueError(f"sem_ia.bullets_por_tipo sem {declaracao.tipo_bloco}")
                if declaracao.max_bullets < self.ia.bullets_min:
                    raise ValueError("max_bullets abaixo de ia.bullets_min")
        return self


def configuracao_gerador(dados: dict | None = None) -> ConfiguracaoGerador:
    return ConfiguracaoGerador.model_validate(dados if dados is not None else carregar("gerador"))
