from __future__ import annotations

import json
from datetime import date

from apoio_geracao import conteudo_ampliado

from src.coletor.contratos import ModeloTrabalho, Senioridade
from src.conteudo.modelo import Equivalencia
from src.triagem.contratos import VagaAguardando, VagaTriagem

HOJE = date(2026, 11, 6)
FAMILIA = "backend_arquitetura"
DESCRICAO_BOA = (
    "Estagio em backend. Voce vai construir APIs em Python com PostgreSQL, "
    "usando Docker Compose no dia a dia. "
) * 4


def inventario():
    _, inventario = conteudo_ampliado()
    equivalencias = [
        Equivalencia(pedido="Kafka", tem="RabbitMQ", citar="mensageria assincrona"),
        Equivalencia(pedido="Kubernetes", tem="Docker Compose", citar="orquestracao local"),
    ]
    return inventario.model_copy(update={"equivalencias": equivalencias})


def vaga(id: int = 1, **campos) -> VagaTriagem:
    base = {
        "id": id,
        "fonte": "greenhouse",
        "empresa": f"Empresa Ficticia {id}",
        "titulo": f"Estagio em Backend {id}",
        "url": f"https://boards.exemplo.invalid/vaga/{id}",
        "descricao": DESCRICAO_BOA,
        "local": "Remoto",
        "pais": "BR",
        "senioridade": Senioridade.ESTAGIO,
        "modelo": ModeloTrabalho.REMOTO,
        "publicada_em": HOJE,
    }
    base.update(campos)
    return VagaTriagem(**base)


def resposta_valida(**campos) -> dict:
    base = {
        "familia": FAMILIA,
        "idioma": "pt",
        "nota_aderencia": 82,
        "techs_cobertas": ["Python", "PostgreSQL"],
        "techs_equivalentes": [],
        "requisitos_descobertos": [],
        "alertas": [],
        "justificativa": "Pede Python e PostgreSQL, ambos no inventario.",
    }
    base.update(campos)
    return base


def texto_resposta(**campos) -> str:
    return json.dumps(resposta_valida(**campos), ensure_ascii=False)


class RepositorioMemoria:
    def __init__(self, pendentes: list[VagaTriagem] | None = None) -> None:
        self.pendentes_lista = list(pendentes or [])
        self.vistas_lista: list[VagaTriagem] = []
        self.descartes: dict[int, str] = {}
        self.aguardando_lista: dict[int, int] = {}
        self.pontuadas: dict[int, dict] = {}
        self.cache: dict[str, dict] = {}
        self.origens: dict[int, str] = {}
        self.notas_de_descarte: dict[int, int] = {}
        self.vagas: dict[int, VagaTriagem] = {v.id: v for v in self.pendentes_lista}

    def pendentes(self) -> list[VagaTriagem]:
        return [v for v in self.pendentes_lista if v.id not in self._tratadas()]

    def vistas(self) -> list[VagaTriagem]:
        tratadas = [v for v in self.pendentes_lista if v.id in self._tratadas()]
        return [*self.vistas_lista, *tratadas]

    def aguardando(self) -> list[VagaAguardando]:
        return [
            VagaAguardando(self.vagas[id_], nota)
            for id_, nota in self.aguardando_lista.items()
            if id_ not in self.pontuadas and id_ not in self.descartes
        ]

    def _tratadas(self) -> set[int]:
        return set(self.descartes) | set(self.aguardando_lista) | set(self.pontuadas)

    def descartar(self, vaga_id: int, motivo: str, nota: int | None = None) -> None:
        self.descartes[vaga_id] = motivo
        if nota is not None:
            self.notas_de_descarte[vaga_id] = nota

    def confirmar(self) -> None:
        return None

    def triar(self, vaga_id: int, pre_nota: int) -> None:
        self.aguardando_lista[vaga_id] = pre_nota

    def pontuar(self, vaga_id: int, nota: int, registro: dict, origem: str) -> None:
        self.pontuadas[vaga_id] = registro
        self.origens[vaga_id] = origem
        self.cache.setdefault(registro["hash_entrada"], registro["resultado"])

    def resultado_em_cache(self, hash_entrada: str) -> dict | None:
        return self.cache.get(hash_entrada)
