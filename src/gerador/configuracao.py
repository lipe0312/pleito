from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from src.config import carregar
from src.conteudo.modelo import Estrito, Identificador, TipoBloco


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
    max_chars: int = Field(gt=0)


class SlotListaTexto(Estrito):
    tipo: Literal["lista_texto"]
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


class ConfiguracaoGerador(Estrito):
    templates: Templates
    jinja: Delimitadores
    travado: ConfiguracaoTravado
    slots: dict[Identificador, DeclaracaoSlot] = Field(min_length=1)
    compilacao: Compilacao

    @model_validator(mode="after")
    def _slot_nao_usa_nome_do_travado(self) -> ConfiguracaoGerador:
        if set(self.slots) & set(self.travado.nomes):
            raise ValueError("slot com o mesmo nome de um dado travado")
        return self


def configuracao_gerador(dados: dict | None = None) -> ConfiguracaoGerador:
    return ConfiguracaoGerador.model_validate(dados if dados is not None else carregar("gerador"))
