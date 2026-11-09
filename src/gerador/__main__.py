from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from src.config import ambiente
from src.conteudo.arquivo import ler_blocos, ler_inventario
from src.conteudo.configuracao import configuracao_conteudo
from src.gerador.configuracao import ConfiguracaoGerador, configuracao_gerador
from src.gerador.laco import (
    PedidoDeGeracao,
    RefacaoRecusada,
    ResultadoDoLaco,
    executar_laco,
    refazer,
)
from src.gerador.pendencia import carregar_vaga, inserir_pendencia
from src.gerador.registro import ler_historico, ler_json
from src.gerador.travado import carregar_travado
from src.llm.roteador import Roteador
from src.validador.analise import Vaga
from src.validador.dados import carregar_banco, carregar_vocabulario


def _argumentos(argv: Sequence[str]) -> argparse.Namespace:
    leitor = argparse.ArgumentParser(prog="make gerar")
    leitor.add_argument("--vaga", type=int, required=True)
    leitor.add_argument("--familia")
    leitor.add_argument("--idioma")
    leitor.add_argument("--refazer", metavar="MOTIVO")
    return leitor.parse_args(argv)


def pasta_da_vaga(pasta_dados: Path, vaga_id: int, config: ConfiguracaoGerador) -> Path:
    return pasta_dados / config.laco.pasta_vagas / str(vaga_id)


def _resumo(resultado: ResultadoDoLaco, config: ConfiguracaoGerador) -> str:
    linhas = [f"estado: {resultado.estado}"]
    for tentativa in resultado.tentativas:
        meta = ler_json(tentativa.pasta / config.laco.arquivos.meta)
        bloqueios = ", ".join(meta["regras"]["bloqueios"]) or "nenhum"
        linhas.append(
            f"tentativa {tentativa.numero} ({tentativa.origem}, {tentativa.modo}): "
            f"bloqueios {bloqueios}, custo {meta['custo_usd']} USD"
        )
    if resultado.escolhida is not None:
        linhas.append(f"escolhida: tentativa {resultado.escolhida}")
    elif resultado.melhor is not None:
        linhas.append(f"melhor tentativa: {resultado.melhor}")
    if resultado.interrompido:
        linhas.append(f"interrompido: {resultado.interrompido}")
    return "\n".join(linhas)


def executar(
    argv: Sequence[str],
    pasta_dados: Path,
    carregar_vaga: Callable[[int], Vaga],
    criar_roteador: Callable[[], Roteador],
    registrar_pendencia: Callable[[int, str, str, str], None],
) -> int:
    argumentos = _argumentos(argv)
    config = configuracao_gerador()
    pasta = pasta_da_vaga(pasta_dados, argumentos.vaga, config)
    familia, idioma = argumentos.familia, argumentos.idioma
    if argumentos.refazer is not None and not (familia and idioma):
        versoes = ler_historico(pasta, config)["versoes"]
        if versoes:
            familia, idioma = familia or versoes[-1]["familia"], idioma or versoes[-1]["idioma"]
    if not (familia and idioma):
        print("informe --familia e --idioma", file=sys.stderr)
        return 2
    conteudo = configuracao_conteudo()
    blocos = ler_blocos(pasta_dados, conteudo)
    inventario = ler_inventario(pasta_dados, conteudo)
    if blocos is None or inventario is None:
        print("blocos ou inventario ausentes; rode make conteudo", file=sys.stderr)
        return 2
    pedido = PedidoDeGeracao(
        familia=familia,
        idioma=idioma,
        vaga=carregar_vaga(argumentos.vaga),
        blocos=blocos,
        inventario=inventario,
        travado=carregar_travado(pasta_dados, conteudo, config),
        banco=carregar_banco(pasta_dados),
        vocabulario=carregar_vocabulario(pasta_dados),
    )
    prefixo = f"{config.laco.pasta_vagas}/{argumentos.vaga}"

    def pendencia(categoria: str, detalhe: str, link: str) -> None:
        registrar_pendencia(argumentos.vaga, categoria, detalhe, f"{prefixo}/{link}")

    opcoes = {"config": config, "registrar_pendencia": pendencia}
    try:
        if argumentos.refazer is not None:
            resultado = refazer(pedido, pasta, criar_roteador(), argumentos.refazer, **opcoes)
        else:
            resultado = executar_laco(pedido, pasta, criar_roteador(), **opcoes)
    except RefacaoRecusada as erro:
        print(f"refacao recusada: {erro}", file=sys.stderr)
        return 2
    print(_resumo(resultado, config))
    return 0


def main() -> None:
    raise SystemExit(
        executar(sys.argv[1:], ambiente().dados, carregar_vaga, Roteador, inserir_pendencia)
    )


if __name__ == "__main__":
    main()
