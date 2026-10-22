from __future__ import annotations

import ast
from pathlib import Path

from src.config import RAIZ, carregar

METODOS_PROIBIDOS = frozenset({"delete", "trash", "forward", "send", "batchDelete"})
TRECHOS_PROIBIDOS = ("/trash", "/send", "/forward", "batchDelete")
VERBOS_PROIBIDOS = frozenset({"delete"})


def _arquivo_do_modulo(raiz: Path, modulo: str) -> Path:
    return raiz.joinpath(*modulo.split(".")).with_suffix(".py")


def _violacoes_no_arquivo(caminho: Path) -> list[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    encontradas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            if no.func.attr in METODOS_PROIBIDOS:
                encontradas.append(f"{caminho}:{no.lineno} .{no.func.attr}()")
        elif isinstance(no, ast.Constant) and isinstance(no.value, str):
            texto = no.value
            if texto.strip().lower() in VERBOS_PROIBIDOS or any(
                trecho in texto for trecho in TRECHOS_PROIBIDOS
            ):
                encontradas.append(f"{caminho}:{no.lineno} {texto!r}")
    return encontradas


def varrer(raiz: Path, modulo_resumo: str) -> list[str]:
    liberado = _arquivo_do_modulo(raiz, modulo_resumo).resolve()
    violacoes = []
    for caminho in sorted((raiz / "src").rglob("*.py")):
        if caminho.resolve() == liberado:
            continue
        violacoes.extend(_violacoes_no_arquivo(caminho))
    return violacoes


def _modulo_resumo() -> str:
    return carregar("emails")["gmail"]["modulo_resumo"]


def test_src_nao_exclui_nem_envia_fora_do_modulo_de_resumo():
    assert varrer(RAIZ, _modulo_resumo()) == []


def _plantar(raiz: Path, relativo: str, codigo: str) -> None:
    destino = raiz / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(codigo, encoding="utf-8")


def test_chamada_destrutiva_plantada_em_src_e_acusada(tmp_path):
    _plantar(tmp_path, "src/email/rotulos.py", "cliente.trash(mensagem)\n")
    _plantar(tmp_path, "src/coletor/x.py", "http.send(pedido)\nhttp.delete(url)\n")
    _plantar(tmp_path, "src/painel/y.py", "api.users().messages().forward(id=1)\n")
    assert len(varrer(tmp_path, _modulo_resumo())) == 4


def test_rota_destrutiva_em_texto_plantada_e_acusada(tmp_path):
    _plantar(
        tmp_path,
        "src/email/z.py",
        'http.post(base + "/messages/1/trash")\nhttp.request("DELETE", url)\n',
    )
    assert len(varrer(tmp_path, _modulo_resumo())) == 2


def test_envio_dentro_do_modulo_de_resumo_do_config_e_permitido(tmp_path):
    relativo = _arquivo_do_modulo(Path(), _modulo_resumo())
    _plantar(tmp_path, str(relativo), 'cliente.send(resumo)\nhttp.post(base + "/send")\n')
    assert varrer(tmp_path, _modulo_resumo()) == []


def test_o_mesmo_envio_fora_do_modulo_de_resumo_e_acusado(tmp_path):
    _plantar(tmp_path, "src/email/outro.py", "cliente.send(resumo)\n")
    assert varrer(tmp_path, _modulo_resumo()) != []
