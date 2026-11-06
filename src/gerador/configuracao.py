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


class Compilacao(Estrito):
    motor: str
    nome_arquivo: Identificador
    argumentos: list[str]
    ambiente: dict[str, str]
    timeout_s: int = Field(gt=0)
    paginas_max: int = Field(gt=0)

    @model_validator(mode="after")
    def _sem_shell_escape(self) -> Compilacao:
        if "-no-shell-escape" not in self.argumentos:
            raise ValueError("compilacao exige -no-shell-escape")
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
