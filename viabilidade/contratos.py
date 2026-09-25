from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum, StrEnum

CAMPOS_TRIAGEM = (
    "titulo",
    "empresa",
    "url",
    "descricao",
    "local",
    "senioridade",
    "modelo",
    "funcao",
)

LIMITE_DESCRICAO_UTIL = 200


class Senioridade(StrEnum):
    ESTAGIO = "estagio"
    JUNIOR = "junior"
    PLENO = "pleno"
    SENIOR = "senior"
    INDEFINIDA = "indefinida"


class ModeloTrabalho(StrEnum):
    REMOTO = "remoto"
    HIBRIDO = "hibrido"
    PRESENCIAL = "presencial"
    INDEFINIDO = "indefinido"


class Funcao(StrEnum):
    ENGENHARIA = "engenharia"
    DADOS = "dados"
    INFRA = "infra"
    QA = "qa"
    OUTRA = "outra"
    INDEFINIDA = "indefinida"


class Veredito(StrEnum):
    GO = "go"
    GO_COM_RESSALVA = "go_com_ressalva"
    NO_GO = "no_go"
    NAO_TESTADO = "nao_testado"


class MotivoNoGo(StrEnum):
    ROBOTS_PROIBE = "robots_proibe"
    TOS_PROIBE = "tos_proibe"
    EXIGE_LOGIN = "exige_login"
    CAPTCHA = "captcha"
    BLOQUEIO_HTTP = "bloqueio_http"
    SEM_DADOS = "sem_dados"
    CAMPOS_INSUFICIENTES = "campos_insuficientes"
    SEM_PROVA_ENVIO = "sem_prova_envio"


@dataclass(frozen=True, slots=True)
class VagaBruta:
    fonte: str
    id_externo: str
    url: str
    titulo: str
    empresa: str
    descricao: str = ""
    local: str = ""
    pais: str = ""
    senioridade: Senioridade = Senioridade.INDEFINIDA
    modelo: ModeloTrabalho = ModeloTrabalho.INDEFINIDO
    funcao: Funcao = Funcao.INDEFINIDA
    anos_experiencia: int | None = None
    publicada_em: date | None = None
    coletada_em: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.id_externo:
            raise ValueError("id_externo obrigatorio")
        if not self.url.startswith("https://"):
            raise ValueError(f"url precisa ser https: {self.url!r}")
        if not self.titulo.strip():
            raise ValueError("titulo obrigatorio")

    @property
    def hash_conteudo(self) -> str:
        bruto = f"{self.empresa}|{self.titulo}|{self.local}|{self.descricao}".lower()
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()

    @property
    def campos_ausentes(self) -> tuple[str, ...]:
        ausentes = []
        for campo in CAMPOS_TRIAGEM:
            valor = getattr(self, campo)
            if isinstance(valor, Enum):
                if valor.value.startswith("indefinid"):
                    ausentes.append(campo)
            elif isinstance(valor, int):
                pass
            elif not str(valor).strip():
                ausentes.append(campo)
            elif campo == "descricao" and len(str(valor).strip()) < LIMITE_DESCRICAO_UTIL:
                ausentes.append(campo)
        return tuple(ausentes)

    @property
    def completude(self) -> float:
        return 1.0 - len(self.campos_ausentes) / len(CAMPOS_TRIAGEM)


@dataclass(slots=True)
class ResultadoColeta:
    fonte: str
    vagas: list[VagaBruta] = field(default_factory=list)
    http_status: int | None = None
    robots_permite: bool | None = None
    erro: str | None = None
    motivos: list[MotivoNoGo] = field(default_factory=list)
    requer_revisao_tos: bool = False
    duracao_s: float = 0.0
    evidencia: dict = field(default_factory=dict)

    @property
    def completude_media(self) -> float:
        if not self.vagas:
            return 0.0
        return sum(v.completude for v in self.vagas) / len(self.vagas)

    @property
    def unicas(self) -> int:
        return len({v.hash_conteudo for v in self.vagas})

    def veredito(self, minimo_vagas: int = 5, minimo_completude: float = 0.7) -> Veredito:
        if self.robots_permite is False:
            return Veredito.NO_GO
        if self.motivos:
            return Veredito.NO_GO
        if self.erro or not self.vagas:
            return Veredito.NO_GO
        if len(self.vagas) < minimo_vagas or self.completude_media < minimo_completude:
            return Veredito.GO_COM_RESSALVA
        if self.requer_revisao_tos:
            return Veredito.GO_COM_RESSALVA
        return Veredito.GO
