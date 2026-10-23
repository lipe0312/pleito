from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from src.conteudo.configuracao import ConfiguracaoConteudo
from src.conteudo.modelo import (
    Ancora,
    Bloco,
    Blocos,
    Bullet,
    Equivalencia,
    Inventario,
    ItemInventario,
    validar_conteudo,
)

TECH = re.compile(r"\\tech\{((?:[^{}\\]|\\.)*)\}")
SECAO = re.compile(r"\\section\{([^{}]*)\}")
ENTRADA = re.compile(
    r"\\textbf\{(?P<titulo>(?:[^{}\\]|\\.)*)\}(?P<complemento>[^\n]*?)\\hfill(?P<fim>[^\n]*)\n"
    r"\s*\\begin\{itemize\}(?P<itens>.*?)\\end\{itemize\}",
    re.S,
)
ITEM = re.compile(r"\\item(?![A-Za-z])")
HREF = re.compile(r"\\href\{([^{}]*)\}")
BABEL = re.compile(r"\\usepackage\[([^\]]*)\]\{babel\}")
INICIO_DOCUMENTO = re.compile(r"^[ \t]*\\documentclass", re.M)
DOCUMENTO = re.compile(r"\\begin\{document\}(.*?)\\end\{document\}", re.S)
ESCAPE = re.compile(r"\\([_&%#$])")
COMENTARIO = re.compile(r"(?<!\\)%.*$", re.M)
COMANDO = re.compile(r"\\([A-Za-z]+)")
AMBIENTE = re.compile(r"\\(?:begin|end)\{([^{}]*)\}")
CARACTERE_POR_CODIGO = "^^"
TIPOS_COM_BULLETS = ("experiencia", "projeto")


class GuiaInvalido(ValueError):
    pass


class LatexProibido(GuiaInvalido):
    pass


class EstruturaDivergente(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _Entrada:
    titulo: str
    complemento: str
    fim: str
    itens: tuple[str, ...]


@dataclass(slots=True)
class _Versao:
    sobre: str | None = None
    entradas: dict[str, list[_Entrada]] = field(default_factory=dict)


def _sem_escape(texto: str) -> str:
    return ESCAPE.sub(r"\1", texto)


def _linha(texto: str) -> str:
    return " ".join(texto.split())


def _techs(texto: str) -> list[str]:
    return list(dict.fromkeys(_sem_escape(tech).strip() for tech in TECH.findall(texto)))


def _slug(texto: str, palavras_max: int) -> str:
    plano = unicodedata.normalize("NFKD", _sem_escape(texto))
    plano = plano.encode("ascii", "ignore").decode("ascii").lower()
    return "_".join(re.findall(r"[a-z0-9]+", plano)[:palavras_max])


def _trecho(texto: str, titulo: str, ate_proxima_secao: bool) -> str | None:
    linhas = texto.splitlines()
    for indice, linha in enumerate(linhas):
        if linha.startswith("#") and titulo in linha:
            resto = linhas[indice + 1 :]
            if ate_proxima_secao:
                fim = next((i for i, atual in enumerate(resto) if atual.startswith("## ")), None)
                resto = resto[:fim]
            return "\n".join(resto)
    return None


def _exigir_latex_permitido(trecho: str, config: ConfiguracaoConteudo) -> None:
    proibidos = sorted(set(COMANDO.findall(trecho)) - config.latex_comandos_permitidos)
    proibidos += sorted(set(AMBIENTE.findall(trecho)) - config.latex_ambientes_permitidos)
    if CARACTERE_POR_CODIGO in trecho:
        proibidos.append(CARACTERE_POR_CODIGO)
    if proibidos:
        raise LatexProibido(f"latex fora da allowlist: {proibidos}")


def _versao(corpo: str, config: ConfiguracaoConteudo) -> _Versao:
    versao = _Versao()
    partes = SECAO.split(COMENTARIO.sub("", corpo))
    for titulo, conteudo in zip(partes[1::2], partes[2::2], strict=True):
        tipo = config.secoes.get(titulo.strip())
        if tipo is not None:
            _exigir_latex_permitido(conteudo, config)
        if tipo == "sobre":
            versao.sobre = _linha(conteudo)
        elif tipo in TIPOS_COM_BULLETS:
            versao.entradas[tipo] = [
                _Entrada(
                    titulo=m["titulo"].strip(),
                    complemento=m["complemento"].strip().lstrip(",").strip(),
                    fim=m["fim"].strip(),
                    itens=tuple(
                        _linha(item) for item in ITEM.split(m["itens"]) if item.strip()
                    ),
                )
                for m in ENTRADA.finditer(conteudo)
            ]
    return versao


def _versoes(guia: str, config: ConfiguracaoConteudo) -> dict[str, _Versao]:
    base = _trecho(guia, config.secao_base, ate_proxima_secao=False)
    if base is None:
        raise GuiaInvalido(f"guia sem a secao {config.secao_base!r}")
    versoes: dict[str, _Versao] = {}
    for pedaco in INICIO_DOCUMENTO.split(base)[1:]:
        babel = BABEL.search(pedaco)
        documento = DOCUMENTO.search(pedaco)
        if babel is None or documento is None:
            raise GuiaInvalido("documento LaTeX sem babel ou sem begin/end document")
        opcao = babel.group(1).split(",")[-1].strip()
        idioma = config.idiomas_babel.get(opcao)
        if idioma is None or idioma in versoes:
            raise GuiaInvalido(f"idioma do babel nao configurado ou repetido: {opcao!r}")
        versoes[idioma] = _versao(documento.group(1), config)
    if config.idioma_principal not in versoes:
        raise GuiaInvalido(f"guia sem a versao {config.idioma_principal!r} do curriculo")
    return versoes


def _exigir_mesma_estrutura(versoes: dict[str, _Versao], principal: str) -> None:
    referencia = versoes[principal]
    for idioma, versao in versoes.items():
        if (versao.sobre is None) != (referencia.sobre is None):
            raise EstruturaDivergente(f"{idioma}: secao sobre diverge de {principal}")
        for tipo in TIPOS_COM_BULLETS:
            esperadas = referencia.entradas.get(tipo, [])
            atuais = versao.entradas.get(tipo, [])
            if len(atuais) != len(esperadas):
                raise EstruturaDivergente(f"{idioma}: {len(atuais)} entradas de {tipo}")
            for posicao, (atual, esperada) in enumerate(zip(atuais, esperadas, strict=True), 1):
                if len(atual.itens) != len(esperada.itens):
                    raise EstruturaDivergente(
                        f"{idioma}: {tipo} {posicao} tem {len(atual.itens)} bullets"
                    )


def _imutavel(tipo: str, entrada: _Entrada) -> dict[str, str]:
    if tipo == "experiencia":
        cargo, _, empresa = entrada.titulo.partition(", ")
        return {"cargo": cargo, "empresa": empresa, "periodo": entrada.fim}
    link = HREF.search(entrada.fim)
    return {
        "nome": entrada.titulo,
        "descricao": entrada.complemento,
        "link": link.group(1) if link else entrada.fim,
    }


def _novo_id(base: str, usados: set[str]) -> str:
    candidato, sufixo = base, 2
    while candidato in usados:
        candidato, sufixo = f"{base}_{sufixo}", sufixo + 1
    usados.add(candidato)
    return candidato


def _blocos(versoes: dict[str, _Versao], config: ConfiguracaoConteudo) -> Blocos:
    principal = config.idioma_principal
    idiomas = [principal, *(i for i in versoes if i != principal)]
    usados: set[str] = set()
    blocos: list[Bloco] = []
    for tipo, prefixo in config.prefixos_id.items():
        if tipo == "sobre":
            if versoes[principal].sobre is not None:
                blocos.append(
                    Bloco(
                        id=_novo_id(prefixo, usados),
                        tipo="sobre",
                        redacao={i: versoes[i].sobre for i in idiomas},
                        techs=_techs(versoes[principal].sobre),
                    )
                )
            continue
        for posicao, entrada in enumerate(versoes[principal].entradas.get(tipo, [])):
            por_idioma = {i: versoes[i].entradas[tipo][posicao] for i in idiomas}
            imutavel = {i: _imutavel(tipo, e) for i, e in por_idioma.items()}
            nome = imutavel[principal]["empresa" if tipo == "experiencia" else "nome"]
            sufixo = _slug(nome or entrada.titulo, config.palavras_id_max)
            bloco_id = _novo_id(f"{prefixo}_{sufixo}" if sufixo else prefixo, usados)
            bullets = [
                Bullet(
                    id=_novo_id(f"{bloco_id}_{n}", usados),
                    redacao={i: por_idioma[i].itens[n - 1] for i in idiomas},
                    techs=_techs(item),
                )
                for n, item in enumerate(entrada.itens, 1)
            ]
            blocos.append(
                Bloco(
                    id=bloco_id,
                    tipo=tipo,
                    imutavel={
                        campo: {i: imutavel[i][campo] for i in idiomas}
                        for campo in imutavel[principal]
                    },
                    bullets=bullets,
                )
            )
    return Blocos(idiomas=idiomas, blocos=blocos)


def _inventario(blocos: Blocos, guia: str, config: ConfiguracaoConteudo) -> Inventario:
    ancoras: dict[str, list[Ancora]] = {}
    for bloco in blocos.blocos:
        for bullet in bloco.bullets:
            for tech in bullet.techs:
                lista = ancoras.setdefault(tech, [])
                if all(ancora.ref != bloco.id for ancora in lista):
                    lista.append(Ancora(tipo=bloco.tipo, ref=bloco.id, fonte=config.fonte_ancora))
    trecho = _trecho(guia, config.secao_tecnologias, ate_proxima_secao=True) or ""
    equivalencias = [
        Equivalencia(**{chave: valor.strip() for chave, valor in m.groupdict().items()})
        for linha in trecho.splitlines()
        if (m := config.padrao_equivalencia.match(linha.strip()))
    ]
    return Inventario(
        techs=[ItemInventario(tech=tech, ancoras=lista) for tech, lista in ancoras.items()],
        equivalencias=equivalencias,
    )


def decompor(guia: str, config: ConfiguracaoConteudo) -> tuple[Blocos, Inventario]:
    versoes = _versoes(guia, config)
    _exigir_mesma_estrutura(versoes, config.idioma_principal)
    blocos = _blocos(versoes, config)
    inventario = _inventario(blocos, guia, config)
    validar_conteudo(blocos, inventario)
    return blocos, inventario
