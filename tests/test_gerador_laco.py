from __future__ import annotations

import json
import re
from copy import deepcopy

import pytest
from apoio_laco import (
    INJECAO_VALIDADOR,
    com_numero_inventado,
    com_quatro_projetos,
    compilador_falso,
    configuracao,
    pedido,
    roteador_em_sequencia,
    validos,
)

from src.config import carregar
from src.gerador.configuracao import configuracao_gerador
from src.gerador.laco import (
    Estado,
    RefacaoRecusada,
    ResultadoPasso,
    executar_laco,
    refazer,
)
from src.padroes.configuracao import configuracao_padroes
from src.validador.configuracao import configuracao_validador

MARCAS = configuracao_padroes().marcacao


def _rodar(pasta, roteador, compilador=None, config=None, descricao=None, pendencias=None):
    argumentos = {} if descricao is None else {"descricao": descricao}
    return executar_laco(
        pedido(**argumentos),
        pasta,
        roteador,
        config=config or configuracao(),
        compilador=compilador or compilador_falso(),
        registrar_pendencia=(
            (lambda *dados: pendencias.append(dados)) if pendencias is not None else None
        ),
    )


def _fora_das_marcas(texto: str) -> str:
    padrao = re.escape(MARCAS.abre) + r".*?" + re.escape(MARCAS.fecha)
    return re.sub(padrao, "", texto, flags=re.DOTALL)


def _ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_invalido_invalido_valido_termina_na_terceira_tentativa(tmp_path):
    roteador, rastro = roteador_em_sequencia(
        [com_numero_inventado(), com_numero_inventado(), validos()]
    )

    resultado = _rodar(tmp_path, roteador)

    assert resultado.estado is Estado.APROVADO
    assert len(rastro.pedidos) == 3
    assert resultado.escolhida == 3
    assert [t.resultado.aprovado for t in resultado.tentativas] == [False, False, True]
    assert (tmp_path / "cv.pdf").is_file()
    assert (tmp_path / "cv.tex").read_text() == (tmp_path / "tentativas/3/cv.tex").read_text()


def test_sempre_invalido_vira_curriculo_invalido_depois_de_tentativas_max(tmp_path):
    roteador, rastro = roteador_em_sequencia([com_numero_inventado()])
    pendencias = []

    resultado = _rodar(
        tmp_path, roteador, config=configuracao(tentativas_max=2), pendencias=pendencias
    )

    assert resultado.estado is Estado.CURRICULO_INVALIDO
    assert len(rastro.pedidos) == 2
    assert len(rastro.reservas) == 2
    assert resultado.melhor in {1, 2}
    assert len(pendencias) == 1
    categoria, detalhe, link = pendencias[0]
    assert categoria == "curriculo_invalido"
    assert "V11" in detalhe
    assert link.endswith(f"tentativas/{resultado.melhor}")
    assert not (tmp_path / "cv.pdf").exists()


def test_tentativas_max_vem_da_configuracao(tmp_path):
    roteador, rastro = roteador_em_sequencia([com_numero_inventado()])

    _rodar(tmp_path, roteador, config=configuracao(tentativas_max=4))

    assert len(rastro.pedidos) == 4


def test_orcamento_esgotado_entre_a_primeira_e_a_segunda_tentativa_para_sem_chamar(tmp_path):
    roteador, rastro = roteador_em_sequencia([com_numero_inventado()], esgota_na_reserva=2)
    pendencias = []

    resultado = _rodar(tmp_path, roteador, pendencias=pendencias)

    assert len(rastro.pedidos) == 1
    assert len(rastro.reservas) == 1
    assert rastro.pedidos_de_reserva == 2
    assert resultado.estado is Estado.ADIADO
    assert len(resultado.tentativas) == 1
    assert pendencias == []


def test_cada_chamada_tem_reserva_antes_do_envio(tmp_path):
    roteador, rastro = roteador_em_sequencia([com_numero_inventado()])

    _rodar(tmp_path, roteador)

    assert len(rastro.reservas) == len(rastro.pedidos) == 3
    assert all(reserva["custo_maximo_usd"] > 0 for reserva in rastro.reservas)


def test_pagina_e_meia_resolvida_no_passo_tres_sem_nenhuma_chamada_extra(tmp_path):
    reduzido = configuracao().corte.espaco_vertical.para
    compilador = compilador_falso(paginas=lambda tex: 1 if f"\\vspace{{{reduzido}}}" in tex else 2)
    roteador, rastro = roteador_em_sequencia([validos()])

    resultado = _rodar(tmp_path, roteador, compilador=compilador)

    assert resultado.estado is Estado.APROVADO
    assert len(rastro.pedidos) == 1
    passos = resultado.tentativas[0].corte
    assert [p.passo for p in passos] == [1, 2, 3]
    assert [p.resultado for p in passos] == [
        ResultadoPasso.SEM_EFEITO,
        ResultadoPasso.SEM_EFEITO,
        ResultadoPasso.RESOLVEU,
    ]
    meta = _ler(tmp_path / "tentativas/1/meta.json")
    assert [p["nome"] for p in meta["corte"]] == configuracao().corte.ordem[:3]


def test_quarto_projeto_sai_no_primeiro_passo(tmp_path):
    compilador = compilador_falso(paginas=lambda tex: 2 if "Projeto Epsilon" in tex else 1)
    roteador, _ = roteador_em_sequencia([com_quatro_projetos()])

    resultado = _rodar(tmp_path, roteador, compilador=compilador)

    assert resultado.estado is Estado.APROVADO
    assert resultado.tentativas[0].corte[0].resultado is ResultadoPasso.RESOLVEU
    assert len(_ler(tmp_path / "tentativas/1/slots.json")["projetos"]) == 3


def test_corte_nunca_passa_dos_limites_do_validador_nem_remove_experiencia(tmp_path):
    compilador = compilador_falso(paginas=lambda tex: 2)
    roteador, _ = roteador_em_sequencia([validos()])

    resultado = _rodar(
        tmp_path, roteador, compilador=compilador, config=configuracao(tentativas_max=1)
    )

    limites = configuracao_validador().layout.por_idioma["pt"]
    tex = (tmp_path / "tentativas/1/cv.tex").read_text()
    for valor in re.findall(r"\\linespread\{([0-9.]+)\}", tex):
        assert float(valor) >= limites.linespread_min
    for valor in re.findall(r"(?:top|bottom|margin)=([0-9.]+)cm", tex):
        assert float(valor) * 10 >= limites.margem_min_mm
    slots = _ler(tmp_path / "tentativas/1/slots.json")
    assert len(slots["experiencias"]) == len(validos()["experiencias"])
    assert all(entrada["bullets"] for entrada in slots["experiencias"])
    assert [p.passo for p in resultado.tentativas[0].corte] == [1, 2, 3, 4, 5, 6]
    for passo in resultado.tentativas[0].corte[4:]:
        assert passo.resultado is ResultadoPasso.RECUSADO
        assert passo.regras == ("V17",)
    assert resultado.estado is Estado.CURRICULO_INVALIDO


def test_violacao_volta_para_a_ia_so_com_codigo_e_trecho_marcado(tmp_path):
    roteador, rastro = roteador_em_sequencia([com_numero_inventado(), validos()])

    _rodar(tmp_path, roteador)

    segundo = rastro.pedidos[1]["input"]
    retorno = segundo[len(rastro.pedidos[0]["input"]) :]
    assert "V11" in retorno
    assert "4321" in retorno
    assert "4321" not in _fora_das_marcas(retorno)


def test_vaga_com_injecao_nao_muda_o_resultado_das_regras(tmp_path):
    resposta = com_numero_inventado(INJECAO_VALIDADOR)
    limpo, _ = roteador_em_sequencia([resposta])
    atacado, rastro = roteador_em_sequencia([resposta])

    normal = _rodar(tmp_path / "normal", limpo)
    ataque = _rodar(tmp_path / "ataque", atacado, descricao=f"{INJECAO_VALIDADOR} Python e Docker.")

    codigos = [[v.codigo for v in t.resultado.bloqueios] for t in normal.tentativas]
    assert [[v.codigo for v in t.resultado.bloqueios] for t in ataque.tentativas] == codigos
    assert ataque.estado is normal.estado is Estado.CURRICULO_INVALIDO
    for enviado in rastro.pedidos[1:]:
        assert "IGNORE O VALIDADOR" not in _fora_das_marcas(enviado["input"])


def test_latex_malicioso_no_slot_continua_escapado(tmp_path):
    slots = validos()
    slots["sobre"]["texto"] = r"\input{/etc/passwd} \write18{rm -rf /} " + slots["sobre"]["texto"]
    roteador, _ = roteador_em_sequencia([slots])

    _rodar(tmp_path, roteador, config=configuracao(tentativas_max=1))

    tex = (tmp_path / "tentativas/1/cv.tex").read_text()
    assert "\\input{" not in tex
    assert "\\write18" not in tex


def test_cada_tentativa_grava_seus_arquivos_e_a_escolhida_vai_para_a_raiz(tmp_path):
    roteador, _ = roteador_em_sequencia([com_numero_inventado(), validos()])

    _rodar(tmp_path, roteador)

    for numero in (1, 2):
        pasta = tmp_path / "tentativas" / str(numero)
        for nome in ("slots.json", "cv.tex", "cv.pdf", "validacao.json", "meta.json"):
            assert (pasta / nome).is_file(), (numero, nome)
    for nome in ("cv.tex", "cv.pdf", "diff.json", "validacao.json"):
        assert (tmp_path / nome).is_file()
    meta = _ler(tmp_path / "tentativas/1/meta.json")
    assert meta["modelo"]
    assert meta["prompt_versao"].startswith("gerar_slots_v")
    assert float(meta["custo_usd"]) > 0
    assert meta["regras"]["aprovado"] is False
    assert "V11" in meta["regras"]["bloqueios"]
    assert _ler(tmp_path / "tentativas/2/meta.json")["regras"]["aprovado"] is True


def test_rubrica_abaixo_da_nota_minima_pede_uma_melhoria_dentro_do_limite(tmp_path):
    roteador, rastro = roteador_em_sequencia([validos()])

    resultado = _rodar(tmp_path, roteador, config=configuracao(nota_minima=1.0))

    assert len(rastro.pedidos) == 2
    assert resultado.estado is Estado.APROVADO
    assert [t.origem for t in resultado.tentativas] == ["inicial", "melhoria"]


def test_sem_roteador_gera_sem_ia_e_nao_tenta_de_novo(tmp_path):
    resultado = _rodar(tmp_path, None)

    assert resultado.tentativas[0].modo == "sem_ia"
    assert len(resultado.tentativas) == 1


def test_refacao_gera_versao_nova_e_mantem_as_anteriores(tmp_path):
    roteador, rastro = roteador_em_sequencia([validos()])
    _rodar(tmp_path, roteador)
    primeira = (tmp_path / "tentativas/1/cv.tex").read_text()

    resultado = refazer(
        pedido(),
        tmp_path,
        roteador,
        "Mais foco no projeto de dados",
        config=configuracao(),
        compilador=compilador_falso(),
    )

    assert resultado.estado is Estado.APROVADO
    assert resultado.escolhida == 2
    assert (tmp_path / "tentativas/1/cv.tex").read_text() == primeira
    historico = _ler(tmp_path / "historico.json")
    assert [v["tentativa"] for v in historico["versoes"]] == [1, 2]
    assert historico["refacoes"][0]["motivo"] == "Mais foco no projeto de dados"
    assert "Mais foco no projeto de dados" in rastro.pedidos[-1]["input"]
    assert _ler(tmp_path / "tentativas/2/meta.json")["motivo"] == "Mais foco no projeto de dados"


def test_refacao_alem_de_refacoes_max_e_recusada_sem_chamar(tmp_path):
    roteador, rastro = roteador_em_sequencia([validos()])
    config = configuracao(refacoes_max=1)
    _rodar(tmp_path, roteador, config=config)
    refazer(
        pedido(),
        tmp_path,
        roteador,
        "primeiro ajuste",
        config=config,
        compilador=compilador_falso(),
    )
    chamadas = len(rastro.pedidos)

    with pytest.raises(RefacaoRecusada):
        refazer(
            pedido(),
            tmp_path,
            roteador,
            "segundo ajuste",
            config=config,
            compilador=compilador_falso(),
        )

    assert len(rastro.pedidos) == chamadas
    assert len(_ler(tmp_path / "historico.json")["refacoes"]) == 1


def test_refacao_sem_versao_anterior_ou_sem_motivo_e_recusada(tmp_path):
    roteador, rastro = roteador_em_sequencia([validos()])

    with pytest.raises(RefacaoRecusada):
        refazer(
            pedido(),
            tmp_path,
            roteador,
            "ajuste",
            config=configuracao(),
            compilador=compilador_falso(),
        )
    _rodar(tmp_path, roteador)
    with pytest.raises(RefacaoRecusada):
        refazer(
            pedido(),
            tmp_path,
            roteador,
            "   ",
            config=configuracao(),
            compilador=compilador_falso(),
        )
    with pytest.raises(RefacaoRecusada):
        refazer(
            pedido(),
            tmp_path,
            roteador,
            "x" * (configuracao().laco.motivo_max_chars + 1),
            config=configuracao(),
            compilador=compilador_falso(),
        )
    assert len(rastro.pedidos) == 1


def _validador_com_entrelinha_e_margem():
    dados = deepcopy(carregar("validador"))
    preambulo = dados["latex"]["preambulo"]
    preambulo["comandos"] = [*preambulo["comandos"], "linespread"]
    preambulo["pacotes"]["geometry"] = [
        *preambulo["pacotes"]["geometry"],
        r"(top|bottom)=[0-9]+(\.[0-9]+)?cm",
    ]
    return configuracao_validador(dados)


def test_entrelinha_e_margem_vao_ate_o_minimo_do_validador_e_nao_abaixo(tmp_path):
    compilador = compilador_falso(paginas=lambda tex: 1 if "top=" in tex else 2)
    roteador, rastro = roteador_em_sequencia([validos()])
    validador = _validador_com_entrelinha_e_margem()

    resultado = executar_laco(
        pedido(),
        tmp_path,
        roteador,
        config=configuracao(),
        validador=validador,
        compilador=compilador,
    )

    assert resultado.estado is Estado.APROVADO
    assert len(rastro.pedidos) == 1
    assert [p.resultado for p in resultado.tentativas[0].corte][-2:] == [
        ResultadoPasso.AINDA_ESTOURA,
        ResultadoPasso.RESOLVEU,
    ]
    limites = validador.layout.por_idioma["pt"]
    tex = (tmp_path / "cv.tex").read_text()
    assert f"\\linespread{{{limites.linespread_min:g}}}" in tex
    margem = max(configuracao().corte.margem_vertical_cm, limites.margem_min_mm / 10)
    assert f"top={margem:g}cm,bottom={margem:g}cm" in tex


def test_margem_configurada_abaixo_do_minimo_fica_no_minimo_do_validador(tmp_path):
    compilador = compilador_falso(paginas=lambda tex: 1 if "top=" in tex else 2)
    roteador, _ = roteador_em_sequencia([validos()])
    dados = deepcopy(carregar("gerador"))
    dados["laco"]["nota_minima"] = 0.0
    dados["corte"]["margem_vertical_cm"] = 0.2

    executar_laco(
        pedido(),
        tmp_path,
        roteador,
        config=configuracao_gerador(dados),
        validador=_validador_com_entrelinha_e_margem(),
        compilador=compilador,
    )

    minimo = configuracao_validador().layout.por_idioma["pt"].margem_min_mm / 10
    assert f"top={minimo:g}cm" in (tmp_path / "cv.tex").read_text()
