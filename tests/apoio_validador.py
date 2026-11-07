from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from apoio_gerador import (
    conteudo_ficticio,
    entrada_do_bloco,
    slots_ficticios,
    travado_ficticio,
)

from src.config import carregar
from src.conteudo.modelo import Blocos
from src.gerador.renderizar import renderizar
from src.padroes.configuracao import configuracao_padroes
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador
from src.validador.conteudo import ContextoConteudo, Vaga
from src.validador.documento import ler_documento
from src.validador.texto import plano

VAGA_FICTICIA = Vaga(
    empresa="Acme Ltda",
    titulo="Desenvolvedor Backend",
    descricao=(
        "Buscamos pessoa para manter servicos de dados em ambiente conteinerizado com "
        "testes automatizados e revisao de codigo constante pela equipe inteira"
    ),
)


def configuracao_com(**ajustes) -> ConfiguracaoValidador:
    dados = deepcopy(carregar("validador"))
    for caminho, valor in ajustes.items():
        alvo = dados
        *pais, folha = caminho.split("__")
        for pai in pais:
            alvo = alvo[pai]
        alvo[folha] = valor
    return configuracao_validador(dados)


def inventario_ficticio():
    return conteudo_ficticio()[1]


def tex_ficticio(idioma: str = "pt") -> str:
    blocos, inventario = conteudo_ficticio()
    return renderizar(
        idioma, slots_ficticios(blocos, idioma), travado_ficticio(), blocos, inventario
    )


def tex_com_corpo(extra: str, idioma: str = "pt") -> str:
    tex = tex_ficticio(idioma)
    return tex.replace("\\end{document}", f"{extra}\n\\end{{document}}")


def tex_minimo(corpo: str) -> str:
    return f"\\documentclass{{article}}\n\\begin{{document}}\n{corpo}\n\\end{{document}}\n"


def pdf_minimo(paginas: list[str]) -> bytes:
    total = len(paginas)
    ids = [4 + 2 * i for i in range(total)]
    filhas = " ".join(f"{i} 0 R" for i in ids)
    objetos: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{filhas}] /Count {total} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    for indice, texto in enumerate(paginas):
        pagina, conteudo = ids[indice], ids[indice] + 1
        escapado = texto.encode("cp1252").replace(b"(", b"\\(").replace(b")", b"\\)")
        fluxo = b"BT /F1 12 Tf 50 700 Td (" + escapado + b") Tj ET"
        objetos[pagina] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {conteudo} 0 R >>"
        ).encode()
        objetos[conteudo] = (
            f"<< /Length {len(fluxo)} >>\nstream\n".encode() + fluxo + b"\nendstream"
        )
    saida = bytearray(b"%PDF-1.4\n")
    posicoes = {}
    for numero in sorted(objetos):
        posicoes[numero] = len(saida)
        saida += f"{numero} 0 obj\n".encode() + objetos[numero] + b"\nendobj\n"
    inicio = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode() + b"0000000000 65535 f \n"
    for numero in sorted(objetos):
        saida += f"{posicoes[numero]:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n".encode()
    saida += f"startxref\n{inicio}\n%%EOF\n".encode()
    return bytes(saida)


def gravar_pdf(pasta: Path, paginas: list[str]) -> Path:
    caminho = pasta / "cv.pdf"
    caminho.write_bytes(pdf_minimo(paginas))
    return caminho


def conteudo_rico() -> tuple[Blocos, object]:
    blocos, inventario = conteudo_ficticio()
    base = next(bloco for bloco in blocos.blocos if bloco.id == "proj_projeto_alfa_beta")
    novos = []
    for sufixo, nome in (("gama", "Projeto Gama"), ("delta", "Projeto Delta")):
        imutavel = {campo: dict(por_idioma) for campo, por_idioma in base.imutavel.items()}
        imutavel["nome"] = {idioma: nome for idioma in blocos.idiomas}
        imutavel["link"] = {
            idioma: f"https://example.invalid/{sufixo}" for idioma in blocos.idiomas
        }
        bullets = [
            bullet.model_copy(update={"id": f"proj_{sufixo}_{indice}"})
            for indice, bullet in enumerate(base.bullets, 1)
        ]
        novos.append(
            base.model_copy(
                update={"id": f"proj_{sufixo}", "imutavel": imutavel, "bullets": bullets}
            )
        )
    return blocos.model_copy(update={"blocos": [*blocos.blocos, *novos]}), inventario


def slots_ricos(blocos: Blocos, idioma: str) -> dict:
    slots = slots_ficticios(blocos, idioma)
    por_id = {bloco.id: bloco for bloco in blocos.blocos}
    slots["projetos"] = [
        entrada_do_bloco(por_id[nome], idioma)
        for nome in ("proj_projeto_alfa_beta", "proj_gama", "proj_delta")
    ]
    return slots


def tex_rico(idioma: str = "pt") -> str:
    blocos, inventario = conteudo_rico()
    return renderizar(idioma, slots_ricos(blocos, idioma), travado_ficticio(), blocos, inventario)


def contexto_rico(idioma: str = "pt", vaga: Vaga = VAGA_FICTICIA) -> ContextoConteudo:
    blocos, _ = conteudo_rico()
    return ContextoConteudo(
        blocos=blocos,
        vaga=vaga,
        padroes=configuracao_padroes(),
        travado=travado_ficticio(),
        idioma=idioma,
    )


def inventario_rico():
    return conteudo_rico()[1]


def pdf_posicionado(linhas: list[tuple[float, float, str]], tamanho: float = 10) -> bytes:
    operacoes = b""
    for x, y, texto in linhas:
        escapado = texto.encode("cp1252", "replace").replace(b"(", b"\\(").replace(b")", b"\\)")
        operacoes += f"BT /F1 {tamanho} Tf {x} {y} Td (".encode() + escapado + b") Tj ET\n"
    objetos = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>"
        ),
        5: f"<< /Length {len(operacoes)} >>\nstream\n".encode() + operacoes + b"endstream",
    }
    saida = bytearray(b"%PDF-1.4\n")
    posicoes = {}
    for numero in sorted(objetos):
        posicoes[numero] = len(saida)
        saida += f"{numero} 0 obj\n".encode() + objetos[numero] + b"\nendobj\n"
    inicio = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode() + b"0000000000 65535 f \n"
    for numero in sorted(objetos):
        saida += f"{posicoes[numero]:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n".encode()
    saida += f"startxref\n{inicio}\n%%EOF\n".encode()
    return bytes(saida)


def gravar_pdf_posicionado(pasta: Path, linhas: list[tuple[float, float, str]]) -> Path:
    caminho = pasta / "cv.pdf"
    caminho.write_bytes(pdf_posicionado(linhas))
    return caminho


def gravar_pdf_das_entradas(pasta: Path, tex: str, desloca_data: float = 0) -> Path:
    config = configuracao_validador()
    linhas = []
    y = 780.0
    for secao in ler_documento(tex, config).secoes:
        for entrada in secao.entradas():
            if not entrada.fim:
                continue
            titulo = plano(f"{entrada.titulo} {entrada.complemento}", config)
            linhas.append((40, y, titulo))
            linhas.append((400, y - desloca_data, plano(entrada.fim, config)))
            y -= 30
    return gravar_pdf_posicionado(pasta, linhas)


def log_ficticio(*linhas: str) -> str:
    return "\n".join(("This is pdfTeX, Version fictici", *linhas, "Output written on cv.pdf.", ""))


def gravar_log(pasta: Path, *linhas: str) -> Path:
    caminho = pasta / "cv.log"
    caminho.write_text(log_ficticio(*linhas), encoding="utf-8")
    return caminho
