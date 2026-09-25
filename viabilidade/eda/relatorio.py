from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from viabilidade.contratos import CAMPOS_TRIAGEM, VagaBruta


@dataclass(slots=True)
class Perfil:
    total: int = 0
    unicas: int = 0
    por_fonte: Counter = field(default_factory=Counter)
    por_senioridade: Counter = field(default_factory=Counter)
    por_modelo: Counter = field(default_factory=Counter)
    por_pais: Counter = field(default_factory=Counter)
    por_funcao: Counter = field(default_factory=Counter)
    por_anos: Counter = field(default_factory=Counter)
    campos_ausentes: Counter = field(default_factory=Counter)
    completude_media: float = 0.0
    elegiveis: int = 0

    @property
    def taxa_duplicidade(self) -> float:
        return 0.0 if not self.total else 1.0 - self.unicas / self.total

    @property
    def taxa_elegivel(self) -> float:
        return 0.0 if not self.total else self.elegiveis / self.total


def eh_elegivel(vaga: VagaBruta, senioridades: set[str], modelos: set[str]) -> bool:
    return vaga.senioridade.value in senioridades and vaga.modelo.value in modelos


def perfilar(
    vagas: list[VagaBruta],
    senioridades: set[str] | None = None,
    modelos: set[str] | None = None,
) -> Perfil:
    senioridades = senioridades or {"estagio", "junior"}
    modelos = modelos or {"remoto", "hibrido", "presencial", "indefinido"}
    perfil = Perfil(total=len(vagas), unicas=len({v.hash_conteudo for v in vagas}))
    for vaga in vagas:
        perfil.por_fonte[vaga.fonte] += 1
        perfil.por_senioridade[vaga.senioridade.value] += 1
        perfil.por_modelo[vaga.modelo.value] += 1
        perfil.por_pais[vaga.pais or "desconhecido"] += 1
        perfil.por_funcao[vaga.funcao.value] += 1
        perfil.por_anos[
            "nao declarado" if vaga.anos_experiencia is None
            else ("0 a 2" if vaga.anos_experiencia <= 2 else "3 ou mais")
        ] += 1
        for campo in vaga.campos_ausentes:
            perfil.campos_ausentes[campo] += 1
        if eh_elegivel(vaga, senioridades, modelos):
            perfil.elegiveis += 1
    if vagas:
        perfil.completude_media = sum(v.completude for v in vagas) / len(vagas)
    return perfil


def _tabela(titulo: str, contador: Counter, total: int) -> list[str]:
    linhas = [f"### {titulo}", "", "| valor | n | % |", "| --- | --- | --- |"]
    for chave, n in contador.most_common():
        pct = 0.0 if not total else 100 * n / total
        linhas.append(f"| {chave} | {n} | {pct:.1f} |")
    linhas.append("")
    return linhas


def renderizar_markdown(perfil: Perfil) -> str:
    linhas = [
        "## EDA das vagas coletadas",
        "",
        f"- total coletado: {perfil.total}",
        f"- unicas por hash de conteudo: {perfil.unicas}",
        f"- taxa de duplicidade: {perfil.taxa_duplicidade:.1%}",
        f"- completude media dos campos de triagem: {perfil.completude_media:.1%}",
        f"- elegiveis ao escopo estagio/junior: {perfil.elegiveis} ({perfil.taxa_elegivel:.1%})",
        "",
    ]
    linhas += _tabela("Por fonte", perfil.por_fonte, perfil.total)
    linhas += _tabela("Por senioridade", perfil.por_senioridade, perfil.total)
    linhas += _tabela("Por modelo de trabalho", perfil.por_modelo, perfil.total)
    linhas += _tabela("Por funcao", perfil.por_funcao, perfil.total)
    linhas += _tabela("Por anos de experiencia exigidos", perfil.por_anos, perfil.total)
    linhas += _tabela("Por pais", perfil.por_pais, perfil.total)
    linhas += _tabela("Campos ausentes", perfil.campos_ausentes, perfil.total)
    linhas += [
        f"Campos avaliados na triagem: {', '.join(CAMPOS_TRIAGEM)}.",
        "",
    ]
    return "\n".join(linhas)


def cruzar(vagas: list[VagaBruta]) -> dict[tuple[str, str], int]:
    tabela: dict[tuple[str, str], int] = {}
    for vaga in vagas:
        chave = (vaga.senioridade.value, vaga.modelo.value)
        tabela[chave] = tabela.get(chave, 0) + 1
    return tabela


def avaliar_cenarios(vagas: list[VagaBruta], cenarios: list[dict]) -> list[dict]:
    saida = []
    for cenario in cenarios:
        senioridades = set(cenario["senioridades"])
        modelos = set(cenario["modelos"])
        paises = set(cenario.get("paises") or [])
        funcoes = set(cenario.get("funcoes") or [])
        anos_max = cenario.get("anos_experiencia_max")
        aceitas = [
            v
            for v in vagas
            if v.senioridade.value in senioridades
            and v.modelo.value in modelos
            and (not paises or v.pais in paises)
            and (not funcoes or v.funcao.value in funcoes)
            and (anos_max is None or v.anos_experiencia is None or v.anos_experiencia <= anos_max)
        ]
        unicas = {v.hash_conteudo for v in aceitas}
        saida.append(
            {
                "nome": cenario["nome"],
                "senioridades": sorted(senioridades),
                "modelos": sorted(modelos),
                "paises": sorted(paises) or ["qualquer"],
                "funcoes": sorted(funcoes) or ["qualquer"],
                "vagas": len(aceitas),
                "unicas": len(unicas),
                "taxa": 0.0 if not vagas else len(aceitas) / len(vagas),
                "fontes": sorted({v.fonte for v in aceitas}),
            }
        )
    return saida


def renderizar_cenarios(linhas: list[dict], total: int) -> str:
    saida = [
        "## Cenarios de filtro",
        "",
        f"Avaliados sobre {total} vagas coletadas.",
        "",
        "| cenario | senioridade | modelo | pais | funcao | vagas | unicas | % do total | fontes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for linha in sorted(linhas, key=lambda x: -x["vagas"]):
        saida.append(
            f"| {linha['nome']} | {', '.join(linha['senioridades'])} | "
            f"{', '.join(linha['modelos'])} | {', '.join(linha['paises'])} | "
            f"{', '.join(linha['funcoes'])} | "
            f"{linha['vagas']} | {linha['unicas']} | {linha['taxa']:.1%} | "
            f"{len(linha['fontes'])} |"
        )
    saida.append("")
    return "\n".join(saida)
