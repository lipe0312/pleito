from __future__ import annotations

import re
import tomllib
from pathlib import Path


def alvo(nome):
    makefile = Path("Makefile").read_text(encoding="utf-8")
    achado = re.search(rf"^{nome}:\n((?:\t.*\n?)*)", makefile, re.MULTILINE)
    assert achado, nome
    return achado.group(1)


def test_alvo_auditoria_roda_pip_audit():
    assert "pip_audit" in alvo("auditoria") or "pip-audit" in alvo("auditoria")


def test_auditoria_fora_do_gate_padrao():
    for nome in ("testes", "lint", "testes-banco"):
        assert "auditoria" not in alvo(nome)
        assert "pip_audit" not in alvo(nome)
    hook = Path(".githooks/pre-commit").read_text(encoding="utf-8")
    assert "auditoria" not in hook
    assert "pip_audit" not in hook


def test_pip_audit_e_dependencia_dev():
    dados = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dev = dados["project"]["optional-dependencies"]["dev"]
    assert any(item.startswith("pip-audit") for item in dev)
    assert not any(
        item.startswith("pip-audit") for item in dados["project"]["dependencies"]
    )


def test_seguranca_diz_quando_rodar_auditoria():
    texto = Path("docs/seguranca.md").read_text(encoding="utf-8")
    assert "make auditoria" in texto
