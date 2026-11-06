from __future__ import annotations

from apoio_validador import configuracao_com, gravar_pdf

from src.validador.configuracao import configuracao_validador
from src.validador.paginas import validar_paginas
from src.validador.resultado import Regra


def test_pdf_de_uma_pagina_passa(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia"])

    assert validar_paginas(pdf, configuracao_validador()) == []


def test_pdf_com_duas_paginas_e_recusado(tmp_path):
    pdf = gravar_pdf(tmp_path, ["pagina um", "pagina dois"])

    violacoes = validar_paginas(pdf, configuracao_validador())

    assert [v.regra for v in violacoes] == [Regra.PAGINAS]
    assert "2" in violacoes[0].detalhe


def test_limite_de_paginas_vem_da_configuracao(tmp_path):
    pdf = gravar_pdf(tmp_path, ["pagina um", "pagina dois"])

    assert validar_paginas(pdf, configuracao_com(paginas_max=2)) == []


def test_pdf_ilegivel_e_recusado_em_vez_de_estourar(tmp_path):
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"isto nao e um pdf")

    violacoes = validar_paginas(pdf, configuracao_validador())

    assert [v.regra for v in violacoes] == [Regra.PAGINAS]


def test_pdf_ausente_e_recusado(tmp_path):
    violacoes = validar_paginas(tmp_path / "nao_existe.pdf", configuracao_validador())

    assert [v.regra for v in violacoes] == [Regra.PAGINAS]
