from __future__ import annotations

import pytest
from apoio_validador import (
    contexto_rico,
    gravar_pdf,
    gravar_pdf_das_entradas,
    inventario_rico,
    tex_rico,
)

from src.validador import conteudo
from src.validador.configuracao import configuracao_validador
from src.validador.resultado import CODIGOS, CurriculoInvalido, Regra
from src.validador.validar import exigir_valido, validar_curriculo, validar_fonte

CODIGOS_DESTE_ITEM = {
    "V6",
    "V7",
    "V8",
    "V9",
    "V11",
    "V12",
    "V13",
    "V14",
    "V15",
    "V16",
    "V19",
    "V20",
    "V21",
}


def _bullet(texto):
    return tex_rico().replace("Mantive filas com \\tech{RabbitMQ}.", texto)


CASOS_RUINS = {
    Regra.PREAMBULO: tex_rico().replace("\\pagestyle{empty}", "\\pagestyle{plain}"),
    Regra.CABECALHO: tex_rico().replace("pessoa@exemplo.invalid", "outra@exemplo.invalid"),
    Regra.EXPERIENCIAS: tex_rico().replace("Desenvolvedora Estagiária", "Desenvolvedora Sênior"),
    Regra.EXPERIENCIA_VAZIA: tex_rico().replace(
        "    \\item Reconhecimento com \\tech{face\\_recognition} em hardware de borda.\n", ""
    ),
    Regra.NUMERO: _bullet("Aumentei em 300 por cento a vazao com \\tech{RabbitMQ}."),
    Regra.EMPRESA_DA_VAGA: tex_rico().replace("Estudante de exemplo", "Estudante da Acme"),
    Regra.COPIA_DA_VAGA: _bullet(
        "Atuei para manter servicos de dados em ambiente conteinerizado com testes "
        "automatizados e \\tech{RabbitMQ}."
    ),
    Regra.ESTRUTURA: tex_rico().replace(
        "\\section{Projetos}", "\\section{Skills}\nPython\n\\section{Projetos}"
    ),
    Regra.PROJETOS: tex_rico().replace(
        "\\textbf{Projeto Delta}", "\\textbf{Mais projetos} \\hfill x\n\\textbf{Projeto Delta}"
    ),
    Regra.ESCAPE: tex_rico().replace("face\\_recognition", "face_recognition"),
    Regra.IDIOMA: tex_rico().replace("[brazil]{babel}", "[english]{babel}"),
    Regra.PONTUACAO: _bullet("Mantive filas com \\tech{RabbitMQ}"),
    Regra.SENIORIDADE: _bullet("Liderei o time de filas com \\tech{RabbitMQ}."),
}


def regras(tex, idioma="pt"):
    return {
        v.regra for v in conteudo.validar_conteudo(tex, inventario_rico(), contexto_rico(idioma))
    }


def test_cada_codigo_do_item_tem_um_caso_ruim():
    assert {CODIGOS[regra] for regra in CASOS_RUINS} == CODIGOS_DESTE_ITEM


@pytest.mark.parametrize("regra", list(CASOS_RUINS), ids=lambda regra: CODIGOS[regra])
def test_caso_ruim_dispara_a_regra_dele(regra):
    assert regra in regras(CASOS_RUINS[regra])


@pytest.mark.parametrize("regra", list(CASOS_RUINS), ids=lambda regra: CODIGOS[regra])
def test_desligar_a_regra_faz_o_caso_ruim_passar(monkeypatch, regra):
    config = configuracao_validador()
    analise = conteudo.analisar(CASOS_RUINS[regra], inventario_rico(), contexto_rico(), config)
    sobraram = tuple(
        funcao
        for funcao in conteudo.REGRAS
        if not any(v.regra == regra for v in funcao(analise, config))
    )
    assert len(sobraram) == len(conteudo.REGRAS) - 1
    monkeypatch.setattr(conteudo, "REGRAS", sobraram)

    assert regra not in regras(CASOS_RUINS[regra])


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_template_real_passa_em_todas_as_regras(idioma):
    achados = conteudo.validar_conteudo(tex_rico(idioma), inventario_rico(), contexto_rico(idioma))

    assert achados == []


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_validar_curriculo_com_contexto_aprova_o_template(tmp_path, idioma):
    tex = tex_rico(idioma)
    pdf = gravar_pdf_das_entradas(tmp_path, tex)

    resultado = validar_curriculo(tex, inventario_rico(), pdf=pdf, contexto=contexto_rico(idioma))

    assert resultado.aprovado


def test_validar_curriculo_sem_contexto_nao_existe():
    with pytest.raises(TypeError):
        validar_curriculo(tex_rico(), inventario_rico())


def test_exigir_valido_sem_contexto_nao_existe(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia"])

    with pytest.raises(TypeError):
        exigir_valido(tex_rico(), inventario_rico(), pdf=pdf)


def test_exigir_valido_recusa_violacao_de_conteudo_com_pdf_correto(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia"])

    with pytest.raises(CurriculoInvalido) as erro:
        exigir_valido(
            CASOS_RUINS[Regra.NUMERO], inventario_rico(), pdf=pdf, contexto=contexto_rico()
        )

    assert Regra.NUMERO in erro.value.resultado.regras


def test_validar_curriculo_devolve_codigo_trecho_e_sugestao(tmp_path):
    pdf = gravar_pdf(tmp_path, ["Pessoa Ficticia"])

    resultado = validar_curriculo(
        CASOS_RUINS[Regra.NUMERO], inventario_rico(), pdf=pdf, contexto=contexto_rico()
    )

    achado = [v for v in resultado.violacoes if v.codigo == "V11"]
    assert achado
    assert achado[0].trecho and achado[0].sugestao
    assert not resultado.aprovado


def test_validar_curriculo_junta_regras_de_conteudo_e_as_do_f23(tmp_path):
    pdf = gravar_pdf(tmp_path, ["um", "dois"])
    tex = CASOS_RUINS[Regra.SENIORIDADE].replace("\\end{document}", "\\write18{x}\n\\end{document}")

    resultado = validar_curriculo(tex, inventario_rico(), pdf=pdf, contexto=contexto_rico())

    assert {"V2", "V17", "V21"} <= {v.codigo for v in resultado.violacoes}


def test_sem_contexto_o_comportamento_do_f23_nao_muda():
    assert validar_fonte(tex_rico(), inventario_rico()).aprovado


def test_violacoes_de_conteudo_sempre_trazem_trecho_e_sugestao():
    for regra, tex in CASOS_RUINS.items():
        achados = [
            v
            for v in conteudo.validar_conteudo(tex, inventario_rico(), contexto_rico())
            if v.regra == regra
        ]
        assert achados, regra
        assert all(v.codigo and v.trecho and v.sugestao for v in achados), regra


def test_trecho_respeita_o_limite_da_configuracao():
    limite = configuracao_validador().conteudo.trecho_max_chars
    longo = "x" * (limite * 3)
    tex = tex_rico().replace("Mantive filas com", f"Mantive 777 {longo} com")

    achados = [
        v
        for v in conteudo.validar_conteudo(tex, inventario_rico(), contexto_rico())
        if v.regra == Regra.NUMERO
    ]

    assert achados
    assert all(len(v.trecho) <= limite for v in achados)
