from __future__ import annotations

import os

import pytest
from apoio_validador import (
    configuracao_com,
    contexto_rico,
    gravar_log,
    gravar_pdf,
    gravar_pdf_das_entradas,
    gravar_pdf_posicionado,
    inventario_rico,
    pdf_com_operacoes,
    tex_rico,
)

from src.validador import layout
from src.validador.configuracao import configuracao_validador
from src.validador.resultado import CODIGOS, Regra
from src.validador.validar import validar_curriculo

CODIGOS_DE_LAYOUT = {"V1", "V3", "V4", "V5", "V18"}

OVERFULL = "Overfull \\hbox (12.50pt too wide) in paragraph at lines 31--32"
CONTEXTO_DA_CAIXA = "[]\\T1/lmr/m/n/10 Texto ficticio que estourou a linha"
UNDERFULL = "Underfull \\hbox (badness 10000) in paragraph at lines 40--41"


def codigos(tex, pdf=None, log=None, idioma="pt", config=None):
    resultado = validar_curriculo(
        tex, inventario_rico(), config, pdf, log=log, contexto=contexto_rico(idioma)
    )
    return {v.codigo for v in resultado.violacoes} & CODIGOS_DE_LAYOUT


def violacoes_de(codigo, tex, pdf=None, log=None, idioma="pt", config=None):
    resultado = validar_curriculo(
        tex, inventario_rico(), config, pdf, log=log, contexto=contexto_rico(idioma)
    )
    return [v for v in resultado.violacoes if v.codigo == codigo]


def pdf_coerente(tmp_path, tex=None, desloca_data=0):
    return gravar_pdf_das_entradas(tmp_path, tex or tex_rico(), desloca_data)


def test_cada_codigo_de_layout_tem_uma_regra_ligada():
    assert {CODIGOS[r] for r in Regra if r in CODIGOS} >= CODIGOS_DE_LAYOUT
    assert len(layout.REGRAS_DE_LAYOUT) == len(CODIGOS_DE_LAYOUT)


def test_curriculo_coerente_passa_nas_cinco_regras(tmp_path):
    pdf = pdf_coerente(tmp_path)
    log = gravar_log(tmp_path)

    assert codigos(tex_rico(), pdf, log) == set()


def test_v1_erro_do_pdflatex_vira_violacao_com_as_linhas_do_log(tmp_path):
    log = gravar_log(
        tmp_path, "! Undefined control sequence.", "l.23 \\foo", "                  bar", ""
    )

    achados = violacoes_de("V1", tex_rico(), pdf_coerente(tmp_path), log)

    assert len(achados) == 1
    assert "Undefined control sequence" in achados[0].detalhe
    assert "l.23" in achados[0].trecho
    assert achados[0].sugestao


def test_v1_vale_mesmo_sem_pdf(tmp_path):
    log = gravar_log(tmp_path, "! Emergency stop.", "<*> cv.tex")

    assert "V1" in codigos(tex_rico(), None, log)


def test_v1_limita_a_quantidade_de_erros_reportados(tmp_path):
    erros = [linha for n in range(30) for linha in (f"! Erro numero {n}.", f"l.{n} x")]
    log = gravar_log(tmp_path, *erros)

    achados = violacoes_de("V1", tex_rico(), pdf_coerente(tmp_path), log)

    assert len(achados) == configuracao_validador().layout.log.erros_max


def test_v1_log_explicito_que_nao_existe_e_recusado(tmp_path):
    assert "V1" in codigos(tex_rico(), pdf_coerente(tmp_path), tmp_path / "nao_existe.log")


def test_log_ao_lado_do_pdf_e_lido_sem_ser_informado(tmp_path):
    gravar_log(tmp_path, OVERFULL, CONTEXTO_DA_CAIXA)

    assert "V3" in codigos(tex_rico(), pdf_coerente(tmp_path))


def test_pdf_sem_log_e_recusado_por_v1(tmp_path):
    pdf = pdf_coerente(tmp_path)
    (tmp_path / "cv.log").unlink()

    achados = violacoes_de("V1", tex_rico(), pdf)

    assert len(achados) == 1
    assert "log do pdflatex ausente" in achados[0].detalhe


def test_pdf_sem_log_nao_passa_nem_com_o_resto_perfeito(tmp_path):
    pdf = pdf_coerente(tmp_path)
    (tmp_path / "cv.log").unlink()

    assert codigos(tex_rico(), pdf) == {"V1"}


def test_log_mais_velho_que_o_pdf_nao_vale_e_e_recusado_por_v1(tmp_path):
    pdf = pdf_coerente(tmp_path)
    log = tmp_path / "cv.log"
    velho = pdf.stat().st_mtime - configuracao_validador().layout.log.defasagem_max_s - 60
    os.utime(log, (velho, velho))

    achados = violacoes_de("V1", tex_rico(), pdf)

    assert len(achados) == 1
    assert "mais velho" in achados[0].detalhe


def test_log_de_outra_compilacao_nao_esconde_erro_do_pdf_novo(tmp_path):
    log = gravar_log(tmp_path)
    velho = log.stat().st_mtime - 3600
    os.utime(log, (velho, velho))

    assert "V1" in codigos(tex_rico(), pdf_coerente(tmp_path), log)


def test_log_com_pouca_diferenca_de_hora_para_o_pdf_vale(tmp_path):
    pdf = pdf_coerente(tmp_path)
    log = tmp_path / "cv.log"
    quase = pdf.stat().st_mtime - 1
    os.utime(log, (quase, quase))

    assert codigos(tex_rico(), pdf) == set()


def test_defasagem_maxima_do_log_vem_da_configuracao(tmp_path):
    pdf = pdf_coerente(tmp_path)
    log = tmp_path / "cv.log"
    velho = pdf.stat().st_mtime - 60
    os.utime(log, (velho, velho))
    config = configuracao_com(layout__log__defasagem_max_s=120)

    assert codigos(tex_rico(), pdf, config=config) == set()


def test_v3_overfull_acima_do_limite_e_recusado_com_pagina_e_trecho(tmp_path):
    log = gravar_log(tmp_path, OVERFULL, CONTEXTO_DA_CAIXA, "")

    achados = violacoes_de("V3", tex_rico(), pdf_coerente(tmp_path), log)

    assert len(achados) == 1
    assert "pagina 1" in achados[0].detalhe
    assert "12.50pt" in achados[0].detalhe
    assert "lines 31--32" in achados[0].detalhe
    assert "Texto ficticio" in achados[0].trecho


def test_v3_pagina_do_log_conta_as_paginas_ja_impressas(tmp_path):
    log = gravar_log(tmp_path, "[1{/ficticio/map.map}]", OVERFULL, CONTEXTO_DA_CAIXA)

    achados = violacoes_de("V3", tex_rico(), pdf_coerente(tmp_path), log)

    assert "pagina 2" in achados[0].detalhe


def test_v3_overfull_dentro_do_limite_passa(tmp_path):
    log = gravar_log(
        tmp_path, "Overfull \\hbox (0.40pt too wide) in paragraph at lines 3--4", CONTEXTO_DA_CAIXA
    )

    assert "V3" not in codigos(tex_rico(), pdf_coerente(tmp_path), log)


def test_v3_underfull_acima_do_limite_e_recusado(tmp_path):
    log = gravar_log(tmp_path, UNDERFULL, CONTEXTO_DA_CAIXA)

    assert "V3" in codigos(tex_rico(), pdf_coerente(tmp_path), log)


def test_v3_underfull_leve_passa(tmp_path):
    log = gravar_log(
        tmp_path, "Underfull \\hbox (badness 1200) in paragraph at lines 3--4", CONTEXTO_DA_CAIXA
    )

    assert "V3" not in codigos(tex_rico(), pdf_coerente(tmp_path), log)


def test_v3_limites_vem_da_configuracao(tmp_path):
    log = gravar_log(tmp_path, OVERFULL, UNDERFULL)
    frouxa = configuracao_com(
        layout__log__overfull_max_pt=50, layout__log__underfull_badness_max=10000
    )
    rigida = configuracao_com(layout__log__overfull_max_pt=0, layout__log__underfull_badness_max=0)
    pdf = pdf_coerente(tmp_path)

    assert "V3" not in codigos(tex_rico(), pdf, log, config=frouxa)
    assert len(violacoes_de("V3", tex_rico(), pdf, log, config=rigida)) == 2


def test_v3_limita_a_quantidade_de_caixas_reportadas(tmp_path):
    caixas = []
    for n in range(30):
        caixas += [f"Overfull \\hbox (9.00pt too wide) in paragraph at lines {n}--{n}"]
        caixas += [CONTEXTO_DA_CAIXA, ""]
    log = gravar_log(tmp_path, *caixas)

    achados = violacoes_de("V3", tex_rico(), pdf_coerente(tmp_path), log)

    assert len(achados) == configuracao_validador().layout.log.caixas_max


LOGS_HOSTIS = {
    "bytes_invalidos": b"Overfull \\hbox (\xff\xfe pt too wide)\n! \xc3\x28 erro\n\x00\x01\x02",
    "linha_gigante": ("! " + "A" * 500_000 + "\n").encode(),
    "numero_absurdo": b"Overfull \\hbox (" + b"9" * 4000 + b"pt too wide) in paragraph\n",
    "badness_absurdo": b"Underfull \\hbox (badness " + b"9" * 4000 + b") in paragraph\n",
    "regex_patologica": b"Overfull \\hbox (" + b"1" * 20000 + b".\n" + b"! " * 20000 + b"\n",
    "latex_no_texto": (
        b"Overfull \\hbox (9pt too wide) in paragraph at lines 1--1\n"
        b"[]\\T1/lmr/m/n/10 \\write18{touch /tmp/x} \\input{/etc/passwd} ^^5cinput\n"
    ),
    "so_quebras": b"\r\n" * 5000,
    "vazio": b"",
}


@pytest.mark.parametrize("nome", list(LOGS_HOSTIS))
def test_log_hostil_nunca_derruba_o_validador(tmp_path, nome):
    log = tmp_path / "cv.log"
    log.write_bytes(LOGS_HOSTIS[nome])

    resultado = validar_curriculo(
        tex_rico(),
        inventario_rico(),
        None,
        pdf_coerente(tmp_path),
        log=log,
        contexto=contexto_rico(),
    )

    assert isinstance(resultado.aprovado, bool)
    assert all(
        len(v.trecho) <= configuracao_validador().conteudo.trecho_max_chars
        for v in resultado.violacoes
    )


def test_log_maior_que_o_limite_e_recusado_sem_ler_tudo(tmp_path):
    log = tmp_path / "cv.log"
    log.write_bytes(b"x" * 5000)
    config = configuracao_com(layout__log__tamanho_max_bytes=1000)

    assert "V1" in codigos(tex_rico(), pdf_coerente(tmp_path), log, config=config)


def test_log_com_texto_de_comando_nao_executa_nem_aprova_nada(tmp_path):
    log = tmp_path / "cv.log"
    log.write_bytes(LOGS_HOSTIS["latex_no_texto"])

    assert "V3" in codigos(tex_rico(), pdf_coerente(tmp_path), log)


def test_v4_titulo_e_data_na_mesma_linha_passam(tmp_path):
    assert "V4" not in codigos(tex_rico(), pdf_coerente(tmp_path))


def test_v4_data_abaixo_do_titulo_e_recusada_com_pagina_e_trecho(tmp_path):
    pdf = pdf_coerente(tmp_path, desloca_data=12)

    achados = violacoes_de("V4", tex_rico(), pdf)

    assert achados
    assert "pagina 1" in achados[0].detalhe
    assert "Universidade Exemplo" in achados[0].trecho or "Desenvolvedora" in achados[0].trecho


def test_v4_diferenca_dentro_da_tolerancia_passa(tmp_path):
    folga = configuracao_validador().layout.pdf.tolerancia_de_linha_pt / 2

    assert "V4" not in codigos(tex_rico(), pdf_coerente(tmp_path, desloca_data=folga))


def test_v4_tolerancia_vem_da_configuracao(tmp_path):
    config = configuracao_com(layout__pdf__tolerancia_de_linha_pt=20)

    assert "V4" not in codigos(tex_rico(), pdf_coerente(tmp_path, desloca_data=12), config=config)


def test_v4_titulo_que_quebra_em_duas_linhas_e_recusado(tmp_path):
    pdf = gravar_pdf_posicionado(
        tmp_path,
        [
            (40, 780, "Universidade"),
            (40, 768, "Exemplo"),
            (400, 768, "2020 -- 2024"),
        ],
    )

    assert "V4" in codigos(tex_rico(), pdf)


def test_v4_entrada_que_nao_aparece_no_pdf_e_recusada(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia"])

    achados = violacoes_de("V4", tex_rico(), pdf)

    assert achados
    assert "nao encontrada" in achados[0].detalhe


def test_v5_texto_sem_sobreposicao_passa(tmp_path):
    pdf = gravar_pdf_posicionado(
        tmp_path, [(40, 780, "Primeira linha"), (40, 760, "Segunda linha")]
    )

    assert "V5" not in codigos(tex_rico(), pdf)


def test_v5_linhas_sobrepostas_sao_recusadas_com_pagina_e_trecho(tmp_path):
    pdf = gravar_pdf_posicionado(
        tmp_path, [(40, 780, "Primeira linha"), (40, 777, "Segunda linha")]
    )

    achados = violacoes_de("V5", tex_rico(), pdf)

    assert len(achados) == 1
    assert "pagina 1" in achados[0].detalhe
    assert "Primeira" in achados[0].trecho and "Segunda" in achados[0].trecho


def test_v5_blocos_lado_a_lado_na_mesma_linha_passam(tmp_path):
    pdf = gravar_pdf_posicionado(tmp_path, [(40, 780, "Esquerda"), (400, 780, "Direita")])

    assert "V5" not in codigos(tex_rico(), pdf)


def test_v5_blocos_na_mesma_linha_que_se_cruzam_sao_recusados(tmp_path):
    pdf = gravar_pdf_posicionado(tmp_path, [(40, 780, "Esquerda longa"), (60, 780, "Direita")])

    assert "V5" in codigos(tex_rico(), pdf)


def test_v5_tolerancias_vem_da_configuracao(tmp_path):
    pdf = gravar_pdf_posicionado(
        tmp_path, [(40, 780, "Primeira linha"), (40, 777, "Segunda linha")]
    )
    config = configuracao_com(layout__pdf__sobreposicao_y_min_pt=100)

    assert "V5" not in codigos(tex_rico(), pdf, config=config)


def test_v5_limita_a_quantidade_de_sobreposicoes_reportadas(tmp_path):
    linhas = [(40, 780 - n, f"Linha {n}") for n in range(40)]
    pdf = gravar_pdf_posicionado(tmp_path, linhas)

    assert (
        len(violacoes_de("V5", tex_rico(), pdf))
        == configuracao_validador().layout.pdf.sobreposicoes_max
    )


def test_pdf_ilegivel_nao_derruba_as_regras_de_pdf(tmp_path):
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"isto nao e um pdf")

    assert "V2" in {
        v.codigo
        for v in validar_curriculo(
            tex_rico(), inventario_rico(), None, pdf, contexto=contexto_rico()
        ).violacoes
    }


def test_pdf_com_fluxo_de_conteudo_corrompido_nao_derruba_o_validador(tmp_path):
    pdf = gravar_pdf_posicionado(tmp_path, [(40, 780, "x")])
    bruto = pdf.read_bytes().replace(
        b"BT /F1 10 Tf 40 780 Td (x) Tj ET", b"BT /F9 abc Tf Td () TJ [ ET"
    )
    pdf.write_bytes(bruto)

    assert isinstance(codigos(tex_rico(), pdf), set)


def _com_preambulo(tex, antigo, novo):
    assert antigo in tex
    return tex.replace(antigo, novo)


def test_v18_linespread_abaixo_do_minimo_e_recusado_com_trecho(tmp_path):
    tex = _com_preambulo(
        tex_rico(),
        "\\setlength{\\parindent}{0pt}",
        "\\linespread{0.80}\n\\setlength{\\parindent}{0pt}",
    )

    achados = violacoes_de("V18", tex, pdf_coerente(tmp_path, tex))

    assert len(achados) == 1
    assert "linespread" in achados[0].detalhe
    assert "0.80" in achados[0].trecho
    assert "0.88" in achados[0].sugestao


def test_v18_linespread_no_minimo_passa(tmp_path):
    tex = _com_preambulo(
        tex_rico(),
        "\\setlength{\\parindent}{0pt}",
        "\\linespread{0.88}\n\\setlength{\\parindent}{0pt}",
    )

    assert "V18" not in codigos(tex, pdf_coerente(tmp_path, tex))


def test_v18_minimo_de_linespread_e_por_idioma(tmp_path):
    marca = "\\setlength{\\parindent}{0pt}"
    pt = _com_preambulo(tex_rico("pt"), marca, "\\linespread{0.89}\n" + marca)
    en = _com_preambulo(tex_rico("en"), marca, "\\linespread{0.89}\n" + marca)

    assert "V18" not in codigos(pt, pdf_coerente(tmp_path, pt), idioma="pt")
    assert "V18" in codigos(en, pdf_coerente(tmp_path, en), idioma="en")


def test_v18_minimo_vem_da_configuracao(tmp_path):
    marca = "\\setlength{\\parindent}{0pt}"
    tex = _com_preambulo(tex_rico(), marca, "\\linespread{0.80}\n" + marca)
    config = configuracao_com(layout__por_idioma__pt__linespread_min=0.5)

    assert "V18" not in codigos(tex, pdf_coerente(tmp_path, tex), config=config)


def test_v18_linespread_ilegivel_e_recusado(tmp_path):
    marca = "\\setlength{\\parindent}{0pt}"
    tex = _com_preambulo(tex_rico(), marca, "\\linespread{abc}\n" + marca)

    assert "V18" in codigos(tex, pdf_coerente(tmp_path, tex))


def test_v18_linespread_comentado_nao_conta(tmp_path):
    marca = "\\setlength{\\parindent}{0pt}"
    tex = _com_preambulo(tex_rico(), marca, "% \\linespread{0.10}\n" + marca)

    assert "V18" not in codigos(tex, pdf_coerente(tmp_path, tex))


def test_v18_margem_abaixo_do_minimo_e_recusada(tmp_path):
    tex = _com_preambulo(tex_rico(), "margin=1.5cm", "margin=0.5cm")

    achados = violacoes_de("V18", tex, pdf_coerente(tmp_path, tex))

    assert len(achados) == 1
    assert "margem" in achados[0].detalhe


def test_v18_margem_vertical_no_minimo_passa_e_abaixo_e_recusada(tmp_path):
    ok = _com_preambulo(tex_rico(), "margin=1.5cm", "margin=1.5cm,top=1.0cm")
    ruim = _com_preambulo(tex_rico(), "margin=1.5cm", "margin=1.5cm,bottom=0.9cm")

    assert "V18" not in codigos(ok, pdf_coerente(tmp_path, ok))
    assert "V18" in codigos(ruim, pdf_coerente(tmp_path, ruim))


def test_v18_margem_em_outra_unidade_e_convertida(tmp_path):
    ruim = _com_preambulo(tex_rico(), "margin=1.5cm", "margin=5mm")
    ok = _com_preambulo(tex_rico(), "margin=1.5cm", "margin=12mm")

    assert "V18" in codigos(ruim, pdf_coerente(tmp_path, ruim))
    assert "V18" not in codigos(ok, pdf_coerente(tmp_path, ok))


def test_v18_margem_com_unidade_desconhecida_e_recusada(tmp_path):
    tex = _com_preambulo(tex_rico(), "margin=1.5cm", "margin=3zz")

    assert "V18" in codigos(tex, pdf_coerente(tmp_path, tex))


def test_v18_fonte_abaixo_do_minimo_e_recusada(tmp_path):
    tex = _com_preambulo(tex_rico(), "a4paper,10pt", "a4paper,9pt")

    achados = violacoes_de("V18", tex, pdf_coerente(tmp_path, tex))

    assert len(achados) == 1
    assert "fonte" in achados[0].detalhe


def test_v18_fonte_sem_tamanho_usa_o_padrao_da_classe(tmp_path):
    tex = _com_preambulo(tex_rico(), "[a4paper,10pt]{article}", "[a4paper]{article}")
    config = configuracao_com(layout__fonte_padrao_pt=9)

    assert "V18" not in codigos(tex, pdf_coerente(tmp_path, tex))
    assert "V18" in codigos(tex, pdf_coerente(tmp_path, tex), config=config)


def test_v18_template_real_nao_dispara(tmp_path):
    for idioma in ("pt", "en"):
        tex = tex_rico(idioma)
        assert "V18" not in codigos(tex, pdf_coerente(tmp_path, tex), idioma=idioma)


CASOS_RUINS = {
    "V1": lambda pasta: (
        tex_rico(),
        pdf_coerente(pasta),
        gravar_log(pasta, "! Undefined control sequence.", "l.1 \\x"),
    ),
    "V3": lambda pasta: (
        tex_rico(),
        pdf_coerente(pasta),
        gravar_log(pasta, OVERFULL, CONTEXTO_DA_CAIXA),
    ),
    "V4": lambda pasta: (tex_rico(), pdf_coerente(pasta, desloca_data=12), None),
    "V5": lambda pasta: (
        tex_rico(),
        gravar_pdf_posicionado(pasta, [(40, 780, "Primeira linha"), (40, 777, "Segunda linha")]),
        None,
    ),
    "V18": lambda pasta: (
        _com_preambulo(tex_rico(), "margin=1.5cm", "margin=0.5cm"),
        pdf_coerente(pasta),
        None,
    ),
}


def test_cada_codigo_de_layout_tem_um_caso_ruim():
    assert set(CASOS_RUINS) == CODIGOS_DE_LAYOUT


@pytest.mark.parametrize("codigo", sorted(CASOS_RUINS))
def test_caso_ruim_dispara_o_codigo_dele(tmp_path, codigo):
    tex, pdf, log = CASOS_RUINS[codigo](tmp_path)

    assert codigo in codigos(tex, pdf, log)


@pytest.mark.parametrize("codigo", sorted(CASOS_RUINS))
def test_desligar_a_regra_faz_o_caso_ruim_passar(tmp_path, monkeypatch, codigo):
    tex, pdf, log = CASOS_RUINS[codigo](tmp_path)
    config = configuracao_validador()
    entrada = layout.montar_entrada(tex, pdf, log, contexto_rico(), inventario_rico(), config)
    sobraram = tuple(
        funcao
        for funcao in layout.REGRAS_DE_LAYOUT
        if not any(v.codigo == codigo for v in funcao(entrada, config))
    )
    assert len(sobraram) == len(layout.REGRAS_DE_LAYOUT) - 1
    monkeypatch.setattr(layout, "REGRAS_DE_LAYOUT", sobraram)

    assert codigo not in codigos(tex, pdf, log)


def test_v3_vbox_overfull_e_underfull_acima_do_limite_sao_recusados(tmp_path):
    log = gravar_log(
        tmp_path,
        "Overfull \\vbox (7.00pt too high) has occurred while \\output is active",
        "Underfull \\vbox (badness 10000) has occurred while \\output is active",
    )

    achados = violacoes_de("V3", tex_rico(), pdf_coerente(tmp_path), log)

    assert len(achados) == 2
    assert all("vbox" in v.detalhe for v in achados)


def test_v3_vbox_dentro_do_limite_passa_e_o_limite_vem_da_configuracao(tmp_path):
    log = gravar_log(
        tmp_path,
        "Overfull \\vbox (0.50pt too high) has occurred while \\output is active",
        "Underfull \\vbox (badness 1200) has occurred while \\output is active",
    )
    rigida = configuracao_com(
        layout__log__overfull_vbox_max_pt=0, layout__log__underfull_vbox_badness_max=0
    )
    pdf = pdf_coerente(tmp_path)

    assert "V3" not in codigos(tex_rico(), pdf, log)
    assert len(violacoes_de("V3", tex_rico(), pdf, log, config=rigida)) == 2


def _pdf_hostil(tmp_path, operacoes):
    caminho = tmp_path / "cv.pdf"
    caminho.write_bytes(pdf_com_operacoes(operacoes))
    gravar_log(tmp_path)
    return caminho


COORDENADAS_HOSTIS = {
    "inteiro_gigante": "1 0 0 1 " + "9" * 400 + " 700 Tm (x) Tj",
    "overflow_no_produto": (
        "1"
        + "0" * 200
        + " 0 0 1"
        + "0" * 200
        + " 0 0 Tm 1"
        + "0" * 200
        + " 1"
        + "0" * 200
        + " Td (x) Tj"
    ),
    "tamanho_gigante": "/F1 1" + "0" * 300 + " Tf 1 0 0 1 40 700 Tm (x) Tj",
}


@pytest.mark.parametrize("nome", list(COORDENADAS_HOSTIS))
def test_coordenada_fora_do_intervalo_recusa_em_vez_de_comparar_errado(tmp_path, nome):
    pdf = _pdf_hostil(tmp_path, COORDENADAS_HOSTIS[nome].encode())

    achados = [v for v in violacoes_de("V5", tex_rico(), pdf)]

    assert len(achados) == 1
    assert "posicao do texto nao conferida" in achados[0].detalhe


def test_coordenada_nao_finita_na_geometria_vira_pdf_ilegivel():
    from src.validador import geometria

    with pytest.raises(geometria.PdfIlegivel):
        geometria._numeros([float("inf"), 1], 2)
    with pytest.raises(geometria.PdfIlegivel):
        geometria._numeros([float("nan")], 1)


def test_pdf_com_estrutura_aninhada_sem_fim_nao_derruba_o_validador(tmp_path):
    pdf = _pdf_hostil(tmp_path, b"[" * 20000 + b" TJ")

    assert isinstance(codigos(tex_rico(), pdf), set)


def test_pdf_com_mais_caixas_que_o_teto_e_recusado(tmp_path):
    linhas = [(40, 780 - 12 * n, f"Linha {n}") for n in range(30)]
    pdf = gravar_pdf_posicionado(tmp_path, linhas)
    config = configuracao_com(layout__pdf__caixas_max=10)

    assert "V5" in codigos(tex_rico(), pdf, config=config)
    assert "V5" not in codigos(tex_rico(), pdf)
    achados = violacoes_de("V5", tex_rico(), pdf, config=config)
    assert "10 caixas" in achados[0].detalhe


def test_geometria_e_lida_uma_vez_para_v4_e_v5(tmp_path, monkeypatch):
    from src.validador import layout as modulo

    chamadas = []
    original = modulo.ler_geometria
    monkeypatch.setattr(modulo, "ler_geometria", lambda *a: chamadas.append(1) or original(*a))

    codigos(tex_rico(), pdf_coerente(tmp_path))

    assert len(chamadas) == 1
