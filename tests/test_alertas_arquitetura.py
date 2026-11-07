from __future__ import annotations

import ast
from pathlib import Path

from src.config import RAIZ, carregar

DOMINIO = "linkedin.com"
MODULOS_DE_ALERTA = (
    "src/coletor/alertas_cartao.py",
    "src/coletor/alertas_coleta.py",
    "src/coletor/alertas_config.py",
    "src/coletor/alertas_gatilho.py",
    "src/coletor/email_alertas.py",
)
SCRIPT = "scripts/coletar_alertas.py"
IMPORTS_PROIBIDOS = frozenset(
    {
        "requests",
        "urllib",
        "urllib3",
        "aiohttp",
        "playwright",
        "selenium",
        "webbrowser",
        "socket",
        "subprocess",
        "http",
    }
)
CHAMADAS_HTTP = frozenset(
    {"Client", "AsyncClient", "get", "post", "put", "request", "stream", "send", "urlopen"}
)
IMPORTS_PERMITIDOS_DE_BASE = frozenset({"inferir_modelo", "inferir_pais", "inferir_senioridade"})
ACESSOS_PROIBIDOS_NO_GMAIL = frozenset({"rotular", "arquivar"})


def _raiz_do_import(nome: str) -> str:
    return nome.split(".")[0]


def violacoes_de_cliente_http(caminho: Path) -> list[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    achadas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes = [alias.name for alias in no.names]
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes = [no.module]
            if no.module in {"src.coletor.base", "src.coletor.conformidade"}:
                usados = {alias.name for alias in no.names}
                if no.module.endswith("conformidade") or not usados <= IMPORTS_PERMITIDOS_DE_BASE:
                    achadas.append(f"{caminho}:{no.lineno} importa {no.module}")
        else:
            nomes = []
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id in {"httpx", "requests"}
                and no.func.attr in CHAMADAS_HTTP
            ):
                achadas.append(f"{caminho}:{no.lineno} chama {no.func.value.id}.{no.func.attr}")
        for nome in nomes:
            if _raiz_do_import(nome) in IMPORTS_PROIBIDOS:
                achadas.append(f"{caminho}:{no.lineno} importa {nome}")
    return achadas


def test_modulos_de_alerta_nao_tem_cliente_http_nem_navegador():
    achadas = []
    for relativo in MODULOS_DE_ALERTA:
        achadas.extend(violacoes_de_cliente_http(RAIZ / relativo))
    assert achadas == []


def test_httpx_nos_modulos_de_alerta_so_aparece_para_ler_o_status_do_gmail():
    for relativo in MODULOS_DE_ALERTA:
        arvore = ast.parse((RAIZ / relativo).read_text(encoding="utf-8"))
        usos = {
            no.attr
            for no in ast.walk(arvore)
            if isinstance(no, ast.Attribute)
            and isinstance(no.value, ast.Name)
            and no.value.id == "httpx"
        }
        assert usos <= {"HTTPStatusError", "codes"}, relativo


def test_cliente_http_para_o_linkedin_plantado_e_acusado(tmp_path):
    plantado = tmp_path / "ruim.py"
    plantado.write_text(
        "import httpx\nhttpx.get('https://x/jobs/view/1')\nimport requests\n", encoding="utf-8"
    )
    assert len(violacoes_de_cliente_http(plantado)) == 2


def test_nenhum_arquivo_de_src_nem_de_scripts_tem_o_dominio_do_linkedin_no_codigo():
    achados = []
    for pasta in ("src", "scripts"):
        for caminho in (RAIZ / pasta).rglob("*.py"):
            if DOMINIO in caminho.read_text(encoding="utf-8").lower():
                achados.append(str(caminho))
    assert achados == []


def test_fonte_de_alertas_nao_libera_dominio_na_allowlist_de_coleta():
    fonte = carregar("fontes")["fontes"]["linkedin_alertas"]
    assert fonte["dominios"] == []
    assert fonte["verificar_robots"] is False


def test_script_de_alertas_so_entrega_o_cliente_http_ao_gmail():
    arvore = ast.parse((RAIZ / SCRIPT).read_text(encoding="utf-8"))
    chamadas = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and isinstance(no.func.value, ast.Name)
        and no.func.value.id == "httpx"
    ]
    assert [c.func.attr for c in chamadas] == ["Client"]
    assert not any(IMPORTS_PROIBIDOS & {_raiz_do_import(n) for n in _imports(arvore)})


def _imports(arvore: ast.AST) -> list[str]:
    nomes = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.extend(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.append(no.module)
    return nomes


def test_modulos_de_alerta_nao_chamam_rotular_nem_arquivar():
    for relativo in (*MODULOS_DE_ALERTA, SCRIPT):
        arvore = ast.parse((RAIZ / relativo).read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Attribute):
                assert no.attr not in ACESSOS_PROIBIDOS_NO_GMAIL, relativo


def test_make_coletar_alertas_existe_e_chama_o_script():
    makefile = (RAIZ / "Makefile").read_text(encoding="utf-8")
    assert "\ncoletar-alertas:\n\t$(PY) scripts/coletar_alertas.py" in makefile
    assert "coletar-alertas" in makefile.split("\n.PHONY:")[1].split("\n")[0]


def test_coleta_de_alertas_entra_no_agendamento_do_config():
    from src.agendamento.configuracao import agendamento_do_config

    rotinas = {r.nome: r for r in agendamento_do_config().rotinas}
    rotina = rotinas["alertas_coletar"]
    assert rotina.comando == ("/usr/bin/make", "coletar-alertas")
    assert rotina.intervalo_min == carregar("limites")["horarios"]["alertas_intervalo_min"]
