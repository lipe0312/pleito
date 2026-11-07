from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from src.avaliacao.configuracao import configuracao_avaliacao
from src.avaliacao.conjunto import Conteudo, Entrada, Lote, lotes_do_conjunto
from src.avaliacao.referencia import resposta_de_referencia
from src.avaliacao.relatorio import ABERTURA_EXCLUSIVA, PERMISSAO_ARQUIVO, PERMISSAO_PASTA
from src.config import ambiente
from src.gerador.configuracao import configuracao_gerador
from src.gerador.esquema import esquema_dos_slots
from src.gerador.renderizar import renderizar
from src.gerador.resposta import slots_da_resposta
from src.padroes.configuracao import configuracao_padroes
from src.validador.analise import ContextoConteudo, Vaga
from src.validador.banco import BancoTecnologias, montar_banco
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador
from src.validador.conteudo import validar_conteudo
from src.validador.dados import carregar_banco, carregar_vocabulario
from src.validador.resultado import Nivel, Regra, Violacao
from src.validador.tecnologias import validar_tecnologias
from src.validador.vocabulario import Vocabulario, montar_vocabulario

DENTRO = "dentro_das_metas"
FORA = "fora_das_metas"
CARACTERES_FORA_DO_TEXTO = re.compile(r"[^\w\s.,-]")
TEM_DIGITO = re.compile(r"\d")
SO_LETRAS = re.compile(r"^[^\W\d_]+(?: [^\W\d_]+)*$")


class RelatorioForaDeDados(ValueError):
    pass


def _conhecidas(entrada: Entrada, conteudo: Conteudo, config: ConfiguracaoValidador) -> set[str]:
    nomes = [*config.tecnologias_conhecidas, *config.dicionario_tecnologias]
    nomes += [e.pedido for e in conteudo.inventario.equivalencias]
    return {nome.casefold() for nome in nomes}


def _termos_tecnologia(entrada, conteudo, config) -> list[str]:
    conhecidas = _conhecidas(entrada, conteudo, config)
    return [p for p in entrada.proibidos if p.casefold() in conhecidas]


def _termos_numero(entrada, conteudo, config) -> list[str]:
    return [p for p in entrada.proibidos if TEM_DIGITO.search(p)]


def _termos_palavra(entrada, conteudo, config) -> list[str]:
    conhecidas = _conhecidas(entrada, conteudo, config)
    empresa = entrada.empresa.casefold()
    return [
        p
        for p in entrada.proibidos
        if SO_LETRAS.match(p) and p.casefold() not in conhecidas and p.casefold() not in empresa
    ]


def _termos_empresa(entrada, conteudo, config) -> list[str]:
    return [entrada.empresa]


def _termos_anuncio(entrada, conteudo, config) -> list[str]:
    palavras = CARACTERES_FORA_DO_TEXTO.sub(" ", entrada.texto).split()
    tamanho = config.conteudo.copia_da_vaga.palavras + 2
    return [" ".join(palavras[:tamanho])] if len(palavras) >= tamanho else []


FONTES: dict[str, Callable[..., list[str]]] = {
    "proibidos_tecnologia": _termos_tecnologia,
    "proibidos_numero": _termos_numero,
    "proibidos_palavra": _termos_palavra,
    "empresa": _termos_empresa,
    "anuncio": _termos_anuncio,
}


def _dados_do_lote(
    lote: Lote, pasta_dados: Path | None, config: ConfiguracaoValidador
) -> tuple[BancoTecnologias, Vocabulario]:
    conteudo = lote.conteudo
    banco = carregar_banco(pasta_dados, config) if lote.vagas_reais and pasta_dados else None
    vocabulario = (
        carregar_vocabulario(pasta_dados, config) if lote.vagas_reais and pasta_dados else None
    )
    return (
        banco or montar_banco(conteudo.inventario, None),
        vocabulario or montar_vocabulario(conteudo.blocos, config),
    )


def _curriculo_bom(entrada: Entrada, conteudo: Conteudo) -> str:
    gerador = configuracao_gerador()
    resposta = resposta_de_referencia(conteudo, entrada.idioma, gerador)
    esquema = esquema_dos_slots(gerador)
    slots, _ = slots_da_resposta(
        esquema.model_validate(resposta), conteudo.blocos, conteudo.inventario, gerador
    )
    return renderizar(
        entrada.idioma, slots, conteudo.travado, conteudo.blocos, conteudo.inventario, gerador
    )


def _com_injecao(tex: str, idioma: str, texto: str, config: ConfiguracaoValidador) -> str:
    marcador = f"\\section{{{config.conteudo.secoes[idioma].sobre}}}"
    limpo = CARACTERES_FORA_DO_TEXTO.sub(" ", texto)
    return tex.replace(marcador, f"{marcador}\n{limpo}", 1)


def _violacoes(
    tex: str,
    entrada: Entrada,
    conteudo: Conteudo,
    banco: BancoTecnologias,
    vocabulario: Vocabulario,
    config: ConfiguracaoValidador,
) -> list[Violacao]:
    contexto = ContextoConteudo(
        blocos=conteudo.blocos,
        vaga=Vaga(empresa=entrada.empresa, descricao=entrada.texto, titulo=entrada.titulo),
        padroes=configuracao_padroes(),
        travado=conteudo.travado,
        idioma=entrada.idioma,
        banco=banco,
        vocabulario=vocabulario,
    )
    achados = validar_tecnologias(
        tex, conteudo.inventario, config, banco, vocabulario.do_idioma(entrada.idioma)
    )
    achados += validar_conteudo(tex, conteudo.inventario, contexto, config)
    return achados


def _acusou(achados: list[Violacao], regra: Regra) -> bool:
    return any(a.regra is regra and a.nivel is not Nivel.OK for a in achados)


def _metas(regra: Regra, config: ConfiguracaoValidador):
    return config.calibracao.por_regra.get(regra, config.calibracao.metas)


def _taxa(erros: int, total: int) -> float:
    return round(erros / total, 4) if total else 0.0


def _medida(erros: int, total: int, meta: float) -> dict:
    taxa = _taxa(erros, total)
    return {
        "erros": erros,
        "total": total,
        "taxa": taxa,
        "meta": meta,
        "dentro_da_meta": taxa <= meta,
    }


def calibrar(
    lotes: list[Lote],
    config: ConfiguracaoValidador,
    agora: datetime,
    pasta_dados: Path | None = None,
) -> dict:
    falsos_positivos: dict[Regra, int] = defaultdict(int)
    falsos_negativos: dict[Regra, int] = defaultdict(int)
    injetadas: dict[Regra, int] = defaultdict(int)
    boas = 0
    for lote in lotes:
        banco, vocabulario = _dados_do_lote(lote, pasta_dados, config)
        for entrada in lote.entradas:
            bom = _curriculo_bom(entrada, lote.conteudo)
            boas += 1
            achados = _violacoes(bom, entrada, lote.conteudo, banco, vocabulario, config)
            for regra in {a.regra for a in achados if a.nivel is not Nivel.OK}:
                falsos_positivos[regra] += 1
            for regra, injecao in config.calibracao.injecoes.items():
                if injecao.tipos and entrada.tipo not in injecao.tipos:
                    continue
                modelo = injecao.modelo[entrada.idioma]
                ignorados = {termo.casefold() for termo in injecao.ignorar}
                termos = FONTES[injecao.fonte](entrada, lote.conteudo, config)
                for termo in termos:
                    if termo.casefold() in ignorados:
                        continue
                    ruim = _com_injecao(
                        bom, entrada.idioma, modelo.replace("{termo}", termo), config
                    )
                    achados = _violacoes(ruim, entrada, lote.conteudo, banco, vocabulario, config)
                    injetadas[regra] += 1
                    if not _acusou(achados, regra):
                        falsos_negativos[regra] += 1
    regras = {}
    for regra in sorted({*falsos_positivos, *config.calibracao.injecoes}, key=lambda r: r.value):
        metas = _metas(regra, config)
        dados = {"falso_positivo": _medida(falsos_positivos[regra], boas, metas.falso_positivo_max)}
        if regra in config.calibracao.injecoes:
            dados["falso_negativo"] = _medida(
                falsos_negativos[regra], injetadas[regra], metas.falso_negativo_max
            )
        regras[regra.value] = dados
    fora = [
        nome
        for nome, dados in regras.items()
        if not all(medida["dentro_da_meta"] for medida in dados.values())
    ]
    return {
        "data": agora.isoformat(),
        "amostras_boas": boas,
        "regras": regras,
        "sem_injecao": sorted(r.value for r in Regra if r not in config.calibracao.injecoes),
        "fora_da_meta": fora,
        "veredito": FORA if fora else DENTRO,
    }


def pasta_do_relatorio(pasta_dados: Path, config: ConfiguracaoValidador) -> Path:
    base = pasta_dados.resolve()
    subpasta = Path(config.calibracao.subpasta)
    destino = (base / subpasta).resolve()
    if subpasta.is_absolute() or destino == base or not destino.is_relative_to(base):
        raise RelatorioForaDeDados(f"relatorio de calibracao so pode ir para {base}")
    return destino


def gravar(
    relatorio: dict, pasta_dados: Path, config: ConfiguracaoValidador, agora: datetime
) -> Path:
    pasta = pasta_do_relatorio(pasta_dados, config)
    pasta.mkdir(parents=True, exist_ok=True, mode=PERMISSAO_PASTA)
    caminho = pasta / f"{agora:%Y%m%dT%H%M%S}_calibracao.json"
    descritor = os.open(caminho, ABERTURA_EXCLUSIVA, PERMISSAO_ARQUIVO)
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        json.dump(relatorio, arquivo, ensure_ascii=False, indent=2)
    return caminho


def resumo(relatorio: dict, caminho: Path) -> list[str]:
    linhas = [
        f"calibracao do validador: {relatorio['veredito']}, "
        f"{relatorio['amostras_boas']} curriculos bons"
    ]
    for nome, dados in relatorio["regras"].items():
        partes = []
        for chave, medida in dados.items():
            marca = "ok" if medida["dentro_da_meta"] else "FORA"
            partes.append(
                f"{chave} {medida['erros']}/{medida['total']} ({medida['taxa']:.0%}, meta "
                f"{medida['meta']:.0%}) {marca}"
            )
        linhas.append(f"  {nome}: " + "; ".join(partes))
    linhas.append(
        "  sem injecao (sem falso negativo medido): " + ", ".join(relatorio["sem_injecao"])
    )
    linhas.append(f"relatorio: {caminho}")
    return linhas


def executar(pasta_dados: Path | None = None) -> int:
    pasta_dados = pasta_dados or ambiente().dados
    config = configuracao_validador()
    lotes, _ = lotes_do_conjunto(configuracao_avaliacao(), pasta_dados)
    agora = datetime.now(UTC)
    relatorio = calibrar(lotes, config, agora, pasta_dados)
    caminho = gravar(relatorio, pasta_dados, config, agora)
    print("\n".join(resumo(relatorio, caminho)))
    return 0 if relatorio["veredito"] == DENTRO else 1


def main() -> None:
    sys.exit(executar())


if __name__ == "__main__":
    main()
