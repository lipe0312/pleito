from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from apoio_gerador import conteudo_ficticio, slots_ficticios, travado_ficticio

from src.config import carregar
from src.gerador.renderizar import renderizar
from src.validador.configuracao import ConfiguracaoValidador, configuracao_validador


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
