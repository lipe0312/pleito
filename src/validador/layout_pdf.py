from __future__ import annotations

from collections import defaultdict

from src.validador.configuracao import ConfiguracaoValidador
from src.validador.geometria import Caixa, Leitura
from src.validador.layout_entrada import EntradaDeLayout
from src.validador.resultado import Regra, Violacao
from src.validador.texto import compacto, plano, violacao


def _ler(entrada: EntradaDeLayout, regra: Regra, config: ConfiguracaoValidador):
    if entrada.pdf is None:
        return None, []
    if entrada.geometria is None:
        detalhe = f"{entrada.falha_da_geometria}, posicao do texto nao conferida"
        return None, [violacao(config, regra, detalhe, "", "compile de novo")]
    return entrada.geometria, []


def _cadeia(leitura: Leitura) -> tuple[str, list[float], list[int]]:
    cadeia, ys, paginas = [], [], []
    for fragmento in leitura.fragmentos:
        compactado = compacto(fragmento.texto)
        cadeia.append(compactado)
        ys += [fragmento.y] * len(compactado)
        paginas += [fragmento.pagina] * len(compactado)
    return "".join(cadeia), ys, paginas


def validar_titulo_e_data(
    entrada: EntradaDeLayout, config: ConfiguracaoValidador
) -> list[Violacao]:
    leitura, falhas = _ler(entrada, Regra.TITULO_E_DATA, config)
    if leitura is None:
        return falhas
    cadeia, ys, paginas = _cadeia(leitura)
    tolerancia = config.layout.pdf.tolerancia_de_linha_pt
    achados: list[Violacao] = []
    cursor = 0
    for secao in entrada.analise.documento.secoes:
        for item in secao.entradas():
            titulo = plano(f"{item.titulo} {item.complemento}", config)
            data = plano(item.fim, config)
            procurado = compacto(titulo) + compacto(data)
            if not item.fim or not procurado:
                continue
            legivel = f"{titulo} | {data}"
            inicio = cadeia.find(procurado, cursor)
            if inicio < 0:
                achados.append(
                    violacao(
                        config,
                        Regra.TITULO_E_DATA,
                        "entrada nao encontrada no texto do pdf",
                        legivel,
                        "mantenha o titulo da entrada curto o bastante para a data caber na linha",
                    )
                )
                continue
            fim = inicio + len(procurado)
            cursor = fim
            alturas = ys[inicio:fim]
            if max(alturas) - min(alturas) > tolerancia or len(set(paginas[inicio:fim])) > 1:
                achados.append(
                    violacao(
                        config,
                        Regra.TITULO_E_DATA,
                        f"pagina {paginas[inicio]}, titulo e data em linhas diferentes",
                        legivel,
                        "encurte o titulo ou o complemento para a data ficar na mesma linha",
                    )
                )
    return list(dict.fromkeys(achados))


def _sobrepoe(a: Caixa, b: Caixa, config: ConfiguracaoValidador) -> bool:
    opcoes = config.layout.pdf
    largura = min(a.x1, b.x1) - max(a.x0, b.x0)
    altura = min(a.y1, b.y1) - max(a.y0, b.y0)
    return (
        a.pagina == b.pagina
        and largura > opcoes.sobreposicao_x_min_pt
        and (altura > opcoes.sobreposicao_y_min_pt)
    )


def _texto_da_linha(leitura: Leitura, caixa: Caixa, config: ConfiguracaoValidador) -> str:
    tolerancia = config.layout.pdf.tolerancia_de_linha_pt
    linhas: dict[float, list[str]] = defaultdict(list)
    for fragmento in leitura.fragmentos:
        if fragmento.pagina == caixa.pagina and abs(fragmento.y - caixa.y_linha) <= tolerancia:
            linhas[fragmento.y].append(fragmento.texto.strip())
    return " ".join(" ".join(partes) for partes in linhas.values())


def validar_sobreposicao(entrada: EntradaDeLayout, config: ConfiguracaoValidador) -> list[Violacao]:
    leitura, falhas = _ler(entrada, Regra.SOBREPOSICAO, config)
    if leitura is None:
        return falhas
    opcoes = config.layout.pdf
    achados: list[Violacao] = []
    ordenadas = sorted(leitura.caixas, key=lambda c: (c.pagina, c.x0))
    for posicao, a in enumerate(ordenadas):
        for b in ordenadas[posicao + 1 :]:
            if b.pagina != a.pagina or b.x0 - a.x1 > opcoes.sobreposicao_x_min_pt:
                break
            if not _sobrepoe(a, b, config):
                continue
            achados.append(
                violacao(
                    config,
                    Regra.SOBREPOSICAO,
                    f"pagina {a.pagina}, caixas de texto sobrepostas",
                    " | ".join(_texto_da_linha(leitura, c, config) for c in (a, b)),
                    "aumente o espaco entre as linhas ou reduza o conteudo",
                )
            )
        if len(achados) >= opcoes.sobreposicoes_max:
            break
    return list(dict.fromkeys(achados))[: opcoes.sobreposicoes_max]
