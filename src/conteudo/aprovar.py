from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from src.config import ambiente
from src.conteudo.arquivo import destino_conteudo, escrever, ler_blocos, ler_inventario
from src.conteudo.configuracao import ConfiguracaoConteudo, configuracao_conteudo
from src.conteudo.modelo import (
    Ancora,
    Bloco,
    Blocos,
    Inventario,
    ItemInventario,
    validar_conteudo,
)
from src.conteudo.sincronizacao import ConfiguracaoSincronizacao, configuracao_sincronizacao
from src.conteudo.sugestoes import Sugestao, Sugestoes, carregar_sugestoes, gravar_sugestoes


class SugestaoInexistente(LookupError):
    pass


class JaDecidida(ValueError):
    pass


class ProjetoNaoAprovado(ValueError):
    pass


def _pendente(
    sugestao_id: str,
    pasta_dados: Path,
    config: ConfiguracaoConteudo,
    sinc: ConfiguracaoSincronizacao,
) -> tuple[Sugestoes, Sugestao]:
    sugestoes = carregar_sugestoes(pasta_dados, config, sinc)
    alvo = (
        next((s for s in sugestoes.sugestoes if s.id == sugestao_id), None) if sugestoes else None
    )
    if alvo is None:
        raise SugestaoInexistente(f"sugestao {sugestao_id} nao existe em {sinc.arquivo_sugestoes}")
    if alvo.status != "pendente":
        raise JaDecidida(f"sugestao {sugestao_id} ja foi {alvo.status}")
    return sugestoes, alvo


def _registrar(sugestoes: Sugestoes, alvo: Sugestao, **campos) -> tuple[Sugestao, Sugestoes]:
    decidida = alvo.model_copy(update=campos)
    lista = [decidida if s.id == alvo.id else s for s in sugestoes.sugestoes]
    return decidida, sugestoes.model_copy(update={"sugestoes": lista})


def _com_projeto(blocos: Blocos | None, alvo: Sugestao, config: ConfiguracaoConteudo) -> Blocos:
    if blocos is None:
        principal = config.idioma_principal
        idiomas = [principal, *sorted(set(config.idiomas_babel.values()) - {principal})]
        blocos = Blocos(idiomas=idiomas, blocos=[])
    if any(bloco.id == alvo.projeto.id for bloco in blocos.blocos):
        raise ValueError(f"bloco {alvo.projeto.id} ja existe")
    projeto = alvo.projeto
    novo = Bloco(
        id=projeto.id,
        tipo="projeto",
        imutavel={
            "nome": {i: projeto.nome for i in blocos.idiomas},
            "descricao": {i: projeto.descricao or projeto.nome for i in blocos.idiomas},
            "link": {i: projeto.url for i in blocos.idiomas},
        },
    )
    return Blocos(idiomas=blocos.idiomas, blocos=[*blocos.blocos, novo])


def _com_ancora(inventario: Inventario | None, ancora: Ancora, tech: str) -> Inventario:
    itens = list(inventario.techs) if inventario else []
    equivalencias = list(inventario.equivalencias) if inventario else []
    posicao = next((i for i, item in enumerate(itens) if item.tech.lower() == tech.lower()), None)
    if posicao is None:
        itens.append(ItemInventario(tech=tech, ancoras=[ancora]))
    elif ancora not in itens[posicao].ancoras:
        atual = itens[posicao]
        itens[posicao] = ItemInventario(tech=atual.tech, ancoras=[*atual.ancoras, ancora])
    return Inventario(techs=itens, equivalencias=equivalencias)


def aprovar(
    sugestao_id: str,
    por: str,
    agora: datetime,
    pasta_dados: Path,
    config: ConfiguracaoConteudo,
    sinc: ConfiguracaoSincronizacao,
) -> Sugestao:
    if not por.strip():
        raise ValueError("informe quem aprova")
    sugestoes, alvo = _pendente(sugestao_id, pasta_dados, config, sinc)
    destino = destino_conteudo(pasta_dados, config)
    blocos = ler_blocos(pasta_dados, config)
    inventario = ler_inventario(pasta_dados, config)
    if alvo.tipo == "projeto_novo":
        blocos = _com_projeto(blocos, alvo, config)
        validar_conteudo(blocos, inventario or Inventario(techs=[]))
        escrever(destino / config.arquivo_blocos, blocos)
    elif alvo.tipo == "tecnologia_nova":
        existe = blocos and any(
            b.id == alvo.ancora.ref and b.tipo == "projeto" for b in blocos.blocos
        )
        if not existe:
            raise ProjetoNaoAprovado(f"aprove antes o projeto {alvo.ancora.ref}")
        inventario = _com_ancora(inventario, alvo.ancora, alvo.tech)
        validar_conteudo(blocos, inventario)
        escrever(destino / config.arquivo_inventario, inventario)
    decidida, atualizadas = _registrar(
        sugestoes,
        alvo,
        status="aprovada",
        decidida_por=por.strip(),
        decidida_em=agora.isoformat(),
    )
    gravar_sugestoes(atualizadas, pasta_dados, config, sinc)
    return decidida


def rejeitar(
    sugestao_id: str,
    por: str,
    motivo: str,
    agora: datetime,
    pasta_dados: Path,
    config: ConfiguracaoConteudo,
    sinc: ConfiguracaoSincronizacao,
) -> Sugestao:
    if not por.strip():
        raise ValueError("informe quem rejeita")
    if not motivo.strip():
        raise ValueError("informe o motivo da rejeicao")
    sugestoes, alvo = _pendente(sugestao_id, pasta_dados, config, sinc)
    decidida, atualizadas = _registrar(
        sugestoes,
        alvo,
        status="rejeitada",
        decidida_por=por.strip(),
        decidida_em=agora.isoformat(),
        motivo=motivo.strip(),
    )
    gravar_sugestoes(atualizadas, pasta_dados, config, sinc)
    return decidida


def _listar(sugestoes: Sugestoes | None) -> None:
    pendentes = [s for s in sugestoes.sugestoes if s.status == "pendente"] if sugestoes else []
    for s in pendentes:
        print(f"{s.id}  {s.tipo}  {s.projeto.nome}  {s.tech or ''}  {s.projeto.url}")
    print(f"{len(pendentes)} pendentes")


def executar(argv: Sequence[str], pasta_dados: Path, agora: datetime) -> int:
    parser = argparse.ArgumentParser(prog="conteudo-aprovar")
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--id")
    parser.add_argument("--por", default="")
    parser.add_argument("--rejeitar", action="store_true")
    parser.add_argument("--motivo", default="")
    opcoes = parser.parse_args(argv)
    config, sinc = configuracao_conteudo(), configuracao_sincronizacao()
    if opcoes.listar:
        _listar(carregar_sugestoes(pasta_dados, config, sinc))
        return 0
    if not opcoes.id or not opcoes.por.strip():
        print("use --listar, ou --id e --por (e --motivo com --rejeitar)", file=sys.stderr)
        return 2
    if opcoes.rejeitar and not opcoes.motivo.strip():
        print("rejeitar exige --motivo", file=sys.stderr)
        return 2
    try:
        if opcoes.rejeitar:
            rejeitar(opcoes.id, opcoes.por, opcoes.motivo, agora, pasta_dados, config, sinc)
        else:
            aprovar(opcoes.id, opcoes.por, agora, pasta_dados, config, sinc)
    except (SugestaoInexistente, ValueError) as erro:
        print(f"recusado: {erro}", file=sys.stderr)
        return 1
    print(f"{opcoes.id} {'rejeitada' if opcoes.rejeitar else 'aprovada'} por {opcoes.por.strip()}")
    return 0


def main() -> None:
    raise SystemExit(executar(sys.argv[1:], ambiente().dados, datetime.now(UTC)))


if __name__ == "__main__":
    main()
