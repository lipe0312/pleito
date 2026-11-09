from __future__ import annotations

from decimal import Decimal

import pytest
from apoio_painel_curriculos import (
    PDF_BYTES,
    SLOTS_BASE,
    gravar_json,
    gravar_versao,
    pasta_da_familia,
    pasta_da_vaga,
    violacao,
)

from src.painel.curriculos import RepositorioArquivosCurriculos


@pytest.fixture
def repositorio(tmp_path):
    return RepositorioArquivosCurriculos(tmp_path)


def vaga(repositorio, ident="7"):
    return next(c for c in repositorio.curriculos() if c.tipo == "vaga" and c.id == ident)


def test_selo_funcional_quando_tem_pdf_e_nenhuma_regra_bloqueia(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), violacoes=[violacao("ok")])
    assert vaga(repositorio).funcional is True


def test_selo_nao_sai_com_uma_regra_que_bloqueia(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), violacoes=[violacao("ok"), violacao("bloqueia")])
    assert vaga(repositorio).funcional is False


def test_selo_sai_com_indicio_porque_o_laco_aprova_sem_bloqueio(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), violacoes=[violacao("indicio")])
    curriculo = vaga(repositorio)
    assert curriculo.funcional is True
    assert [v.nivel for v in curriculo.violacoes] == ["indicio"]


def test_selo_nao_sai_sem_arquivo_de_validacao(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), violacoes=None)
    assert vaga(repositorio).funcional is False


def test_selo_nao_sai_sem_pdf(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), pdf=False)
    curriculo = vaga(repositorio)
    assert curriculo.funcional is False
    assert curriculo.tem_pdf is False


def test_selo_nao_sai_sem_versao_publicada(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), publicada=False)
    curriculo = vaga(repositorio)
    assert curriculo.funcional is False
    assert curriculo.versoes == ()


def test_tentativas_e_custo_somam_as_tentativas_do_laco(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"), custos=("0.0100", "0.0250"))
    curriculo = vaga(repositorio)
    assert curriculo.tentativas == 2
    assert curriculo.custo_usd == Decimal("0.0350")


def test_familia_e_vaga_saem_em_listas_separadas_pelo_tipo(tmp_path, repositorio):
    gravar_versao(pasta_da_familia(tmp_path, "backend_pt"), familia="backend", idioma="pt")
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    tipos = {(c.tipo, c.id) for c in repositorio.curriculos()}
    assert tipos == {("familia", "backend_pt"), ("vaga", "7")}


def test_diff_da_vaga_e_contra_a_familia_de_mesma_familia_e_idioma(tmp_path, repositorio):
    familia = {**SLOTS_BASE, "sobre": {"texto": "Texto antigo da familia.", "techs": ["Python"]}}
    gravar_versao(pasta_da_familia(tmp_path, "backend_pt"), slots=familia)
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    curriculo = vaga(repositorio)
    assert curriculo.base_tipo == "familia"
    assert curriculo.base_rotulo == "backend_arquitetura (pt)"
    [linha] = [d for d in curriculo.diff if d.nome == "sobre"]
    assert any("Texto antigo da familia." in texto for texto in linha.saiu)
    assert any("Texto do sobre da familia." in texto for texto in linha.entrou)


def test_diff_sem_familia_usa_o_diff_json_da_versao_anterior(tmp_path, repositorio):
    anterior = {"sobre": {"antes": {"texto": "Antes.", "techs": []}, "depois": SLOTS_BASE["sobre"]}}
    gravar_versao(pasta_da_vaga(tmp_path, "7"), anterior=anterior)
    curriculo = vaga(repositorio)
    assert curriculo.base_tipo == "anterior"
    assert any("Antes." in texto for d in curriculo.diff for texto in d.saiu)


def test_primeira_versao_sem_familia_nao_inventa_base(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    curriculo = vaga(repositorio)
    assert curriculo.base_tipo == "nenhuma"
    assert curriculo.diff == ()


def test_projetos_usados_saem_dos_slots_publicados(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    assert vaga(repositorio).projetos == ("proj_alfa",)


def test_pasta_com_nome_fora_do_padrao_e_ignorada(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    gravar_versao(pasta_da_vaga(tmp_path, "..sorrateiro"))
    gravar_versao(pasta_da_vaga(tmp_path, "a b"))
    assert [c.id for c in repositorio.curriculos()] == ["7"]


def test_pdf_so_abre_id_que_esta_na_listagem(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    (tmp_path / "segredo.pdf").write_bytes(b"%PDF-1.4 segredo")
    assert repositorio.pdf("vaga", "7") == PDF_BYTES
    assert repositorio.pdf("vaga", "..") is None
    assert repositorio.pdf("vaga", "../segredo") is None
    assert repositorio.pdf("outro", "7") is None
    assert repositorio.pdf("vaga", "99") is None


def test_pdf_acima_do_limite_nao_e_servido(tmp_path, monkeypatch):
    from src.config import carregar

    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    monkeypatch.setitem(carregar("painel")["curriculos"], "pdf_max_bytes", 4)
    assert RepositorioArquivosCurriculos(tmp_path).pdf("vaga", "7") is None


def test_json_corrompido_levanta_erro_de_valor_para_a_tela_mostrar_falha(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    (pasta_da_vaga(tmp_path, "7") / "validacao.json").write_text("{nao e json", encoding="utf-8")
    with pytest.raises(ValueError):
        repositorio.curriculos()


def test_sem_pasta_de_dados_a_listagem_e_vazia(tmp_path, repositorio):
    assert repositorio.curriculos() == []


def test_pasta_que_e_link_simbolico_para_fora_e_ignorada(tmp_path, repositorio):
    fora = tmp_path / "fora"
    gravar_versao(fora)
    raiz = pasta_da_vaga(tmp_path, "7").parent
    raiz.mkdir(parents=True)
    pasta_da_vaga(tmp_path, "7").symlink_to(fora, target_is_directory=True)
    assert repositorio.curriculos() == []
    assert repositorio.pdf("vaga", "7") is None


def test_historico_fora_do_formato_levanta_erro_de_valor(tmp_path, repositorio):
    gravar_versao(pasta_da_vaga(tmp_path, "7"))
    gravar_json(pasta_da_vaga(tmp_path, "7") / "historico.json", {"versoes": [{"sem": "campos"}]})
    with pytest.raises(ValueError):
        repositorio.curriculos()
