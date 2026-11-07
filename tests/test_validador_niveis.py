from __future__ import annotations

import pytest
from apoio_validador import (
    banco_ficticio,
    configuracao_com,
    contexto_com,
    gravar_pdf_das_entradas,
    inventario_rico,
    tex_rico,
)
from pydantic import ValidationError

from src.validador import niveis
from src.validador.configuracao import configuracao_validador
from src.validador.resultado import (
    REGRAS_DE_SEGURANCA,
    CurriculoInvalido,
    Nivel,
    Regra,
    Resultado,
    Violacao,
)
from src.validador.validar import exigir_valido, validar_curriculo, validar_fonte

NIVEIS_PADRAO = {
    Regra.PAGINAS: Nivel.BLOQUEIA,
    Regra.TECNOLOGIA: Nivel.BLOQUEIA,
    Regra.TRAVESSAO: Nivel.BLOQUEIA,
    Regra.LATEX: Nivel.BLOQUEIA,
    Regra.CARACTERE_INVISIVEL: Nivel.BLOQUEIA,
    Regra.ALFABETO: Nivel.BLOQUEIA,
    Regra.PREAMBULO: Nivel.BLOQUEIA,
    Regra.CABECALHO: Nivel.BLOQUEIA,
    Regra.EXPERIENCIAS: Nivel.BLOQUEIA,
    Regra.EXPERIENCIA_VAZIA: Nivel.BLOQUEIA,
    Regra.NUMERO: Nivel.BLOQUEIA,
    Regra.EMPRESA_DA_VAGA: Nivel.BLOQUEIA,
    Regra.COPIA_DA_VAGA: Nivel.INDICIO,
    Regra.ESTRUTURA: Nivel.BLOQUEIA,
    Regra.PROJETOS: Nivel.BLOQUEIA,
    Regra.ESCAPE: Nivel.BLOQUEIA,
    Regra.IDIOMA: Nivel.BLOQUEIA,
    Regra.PONTUACAO: Nivel.INDICIO,
    Regra.SENIORIDADE: Nivel.BLOQUEIA,
    Regra.COMPILACAO: Nivel.BLOQUEIA,
    Regra.CAIXA_ESTOURADA: Nivel.BLOQUEIA,
    Regra.TITULO_E_DATA: Nivel.BLOQUEIA,
    Regra.SOBREPOSICAO: Nivel.BLOQUEIA,
    Regra.LIMITES_DE_LAYOUT: Nivel.BLOQUEIA,
}

SEGURANCA_DO_PLANO = {
    Regra.LATEX,
    Regra.PAGINAS,
    Regra.ALFABETO,
    Regra.CABECALHO,
    Regra.EMPRESA_DA_VAGA,
}

BULLET_COPIADO = (
    "Atuei para manter servicos de dados em ambiente conteinerizado com testes "
    "automatizados e \\tech{RabbitMQ}."
)


def _tex_copiado() -> str:
    return tex_rico().replace("Mantive filas com \\tech{RabbitMQ}.", BULLET_COPIADO)


def _resultado(tmp_path, tex, config=None, **contexto):
    pdf = gravar_pdf_das_entradas(tmp_path, tex)
    return validar_curriculo(tex, inventario_rico(), config, pdf, contexto=contexto_com(**contexto))


def test_niveis_do_repositorio_sao_os_combinados():
    assert dict(configuracao_validador().niveis) == NIVEIS_PADRAO


def test_regras_de_seguranca_do_plano_estao_travadas_no_codigo():
    assert SEGURANCA_DO_PLANO <= REGRAS_DE_SEGURANCA


@pytest.mark.parametrize("regra", sorted(REGRAS_DE_SEGURANCA), ids=lambda regra: regra.value)
@pytest.mark.parametrize("nivel", ["indicio", "ok"])
def test_rebaixar_regra_de_seguranca_pela_configuracao_falha(regra, nivel):
    niveis_do_repositorio = {r.value: n.value for r, n in NIVEIS_PADRAO.items()}
    niveis_do_repositorio[regra.value] = nivel

    with pytest.raises(ValidationError, match="seguranca"):
        configuracao_com(niveis=niveis_do_repositorio)


def test_regra_sem_nivel_na_configuracao_falha():
    parcial = {r.value: n.value for r, n in NIVEIS_PADRAO.items()}
    del parcial["numero"]

    with pytest.raises(ValidationError, match="sem nivel"):
        configuracao_com(niveis=parcial)


def test_nivel_desconhecido_na_configuracao_falha():
    todos = {r.value: n.value for r, n in NIVEIS_PADRAO.items()}
    todos["copia_da_vaga"] = "talvez"

    with pytest.raises(ValidationError):
        configuracao_com(niveis=todos)


def test_regra_de_estilo_e_de_semelhanca_comecam_em_indicio():
    config = configuracao_validador()

    assert config.niveis[Regra.COPIA_DA_VAGA] is Nivel.INDICIO
    assert config.niveis[Regra.PONTUACAO] is Nivel.INDICIO


def test_indicio_nao_recusa_mas_sai_com_codigo_nivel_trecho_regra_e_evidencia(tmp_path):
    resultado = _resultado(tmp_path, _tex_copiado())

    assert resultado.aprovado
    assert Regra.COPIA_DA_VAGA not in {v.regra for v in resultado.bloqueios}
    achado = [v for v in resultado.indicios if v.regra is Regra.COPIA_DA_VAGA]
    assert len(achado) == 1
    assert achado[0].codigo == "V13"
    assert achado[0].nivel is Nivel.INDICIO
    assert "conteinerizado" in achado[0].trecho
    assert achado[0].evidencia
    assert achado[0].sugestao


def test_exigir_valido_nao_recusa_por_indicio(tmp_path):
    tex = _tex_copiado()
    pdf = gravar_pdf_das_entradas(tmp_path, tex)

    exigir_valido(tex, inventario_rico(), None, pdf, contexto=contexto_com())


def test_exigir_valido_recusa_por_bloqueia_mesmo_com_indicio_junto(tmp_path):
    tex = _tex_copiado().replace("Estudante de exemplo", "Estudante da Acme")
    pdf = gravar_pdf_das_entradas(tmp_path, tex)

    with pytest.raises(CurriculoInvalido) as erro:
        exigir_valido(tex, inventario_rico(), None, pdf, contexto=contexto_com())

    assert erro.value.resultado.regras_bloqueadas == (Regra.EMPRESA_DA_VAGA,)
    assert Regra.COPIA_DA_VAGA in erro.value.resultado.regras
    assert "copia_da_vaga" not in str(erro.value)


def _niveis_com(regra: Regra, nivel: Nivel) -> dict:
    todos = {r.value: n.value for r, n in NIVEIS_PADRAO.items()}
    todos[regra.value] = nivel.value
    return todos


@pytest.mark.parametrize(
    ("nivel", "aprovado", "bloqueios", "indicios", "salvos"),
    [
        (Nivel.BLOQUEIA, False, 1, 0, 0),
        (Nivel.INDICIO, True, 0, 1, 0),
        (Nivel.OK, True, 0, 0, 1),
    ],
)
def test_cada_nivel_da_regra_muda_o_veredito_de_um_jeito(
    tmp_path, nivel, aprovado, bloqueios, indicios, salvos
):
    config = configuracao_com(niveis=_niveis_com(Regra.COPIA_DA_VAGA, nivel))

    resultado = _resultado(tmp_path, _tex_copiado(), config)

    da_regra = [v for v in resultado.violacoes if v.regra is Regra.COPIA_DA_VAGA]
    assert resultado.aprovado is aprovado
    assert len([v for v in da_regra if v.nivel is Nivel.BLOQUEIA]) == bloqueios
    assert len([v for v in da_regra if v.nivel is Nivel.INDICIO]) == indicios
    assert len([v for v in da_regra if v.nivel is Nivel.OK]) == salvos


def test_exigir_valido_recusa_quando_a_configuracao_sobe_a_regra_para_bloqueia(tmp_path):
    config = configuracao_com(niveis=_niveis_com(Regra.COPIA_DA_VAGA, Nivel.BLOQUEIA))
    tex = _tex_copiado()
    pdf = gravar_pdf_das_entradas(tmp_path, tex)

    with pytest.raises(CurriculoInvalido):
        exigir_valido(tex, inventario_rico(), config, pdf, contexto=contexto_com())


def test_aplicar_niveis_ignorado_deixaria_o_indicio_recusar(monkeypatch, tmp_path):
    monkeypatch.setattr(niveis, "aplicar_niveis", lambda violacoes, config: list(violacoes))

    resultado = _resultado(tmp_path, _tex_copiado())

    assert not resultado.aprovado


def test_nivel_da_configuracao_so_rebaixa_nunca_sobe_o_que_a_regra_decidiu():
    config = configuracao_validador()
    fraca = Violacao(Regra.TECNOLOGIA, "x", nivel=Nivel.INDICIO)

    assert niveis.aplicar_niveis([fraca], config)[0].nivel is Nivel.INDICIO


def test_regra_em_ok_na_configuracao_registra_sem_recusar():
    config = configuracao_com(niveis=_niveis_com(Regra.NUMERO, Nivel.OK))
    achado = Violacao(Regra.NUMERO, "x", "trecho", "sugestao")

    saida = niveis.aplicar_niveis([achado], config)

    assert saida[0].nivel is Nivel.OK
    assert "ok" in saida[0].evidencia
    assert Resultado(tuple(saida)).aprovado


def test_resultado_separa_bloqueios_indicios_e_salvos():
    resultado = Resultado(
        (
            Violacao(Regra.NUMERO, "a"),
            Violacao(Regra.PONTUACAO, "b", nivel=Nivel.INDICIO),
            Violacao(Regra.TECNOLOGIA, "c", nivel=Nivel.OK),
        )
    )

    assert [v.detalhe for v in resultado.bloqueios] == ["a"]
    assert [v.detalhe for v in resultado.indicios] == ["b"]
    assert [v.detalhe for v in resultado.salvos] == ["c"]
    assert not resultado.aprovado
    assert resultado.regras_bloqueadas == (Regra.NUMERO,)


def test_so_indicio_e_salvo_aprova():
    resultado = Resultado(
        (
            Violacao(Regra.PONTUACAO, "b", nivel=Nivel.INDICIO),
            Violacao(Regra.TECNOLOGIA, "c", nivel=Nivel.OK),
        )
    )

    assert resultado.aprovado


def test_violacao_de_seguranca_recusa_mesmo_com_tudo_mais_em_indicio(tmp_path):
    tex = tex_rico().replace("\\end{document}", "\\write18{x}\n\\end{document}")

    resultado = _resultado(tmp_path, tex)

    assert not resultado.aprovado
    assert Regra.LATEX in resultado.regras_bloqueadas


def test_validar_fonte_aplica_os_niveis_e_o_f23_continua_bloqueando():
    tex = tex_rico().replace("\\end{document}", "\\write18{x}\n\\end{document}")

    resultado = validar_fonte(tex, inventario_rico())

    assert Regra.LATEX in resultado.regras_bloqueadas


def test_tecnologia_com_evidencia_fraca_nao_sobe_para_bloqueia_pelo_teto_da_configuracao():
    tex = tex_rico().replace("Estudante de exemplo", "Estudante de exemplo com Docker")
    banco = banco_ficticio(Docker=["readme"])

    resultado = validar_fonte(tex, inventario_rico(), banco=banco)

    assert resultado.aprovado
    assert [v.regra for v in resultado.indicios] == [Regra.TECNOLOGIA]


@pytest.mark.parametrize("regra", sorted(REGRAS_DE_SEGURANCA), ids=lambda regra: regra.value)
@pytest.mark.parametrize("nivel", [Nivel.INDICIO, Nivel.OK])
def test_violacao_de_seguranca_nunca_sai_abaixo_de_bloqueia_mesmo_se_a_regra_pedir(regra, nivel):
    saida = niveis.aplicar_niveis([Violacao(regra, "x", nivel=nivel)], configuracao_validador())

    assert saida[0].nivel is Nivel.BLOQUEIA
