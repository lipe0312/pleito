from __future__ import annotations

import os
from pathlib import Path


def test_pre_commit_exige_todas_as_verificacoes():
    hook = Path(".githooks/pre-commit")
    conteudo = hook.read_text(encoding="utf-8")
    assert os.access(hook, os.X_OK)
    assert conteudo.index("make testes") < conteudo.index("make lint")
    assert conteudo.index("make lint") < conteudo.index("make testes-banco")


def test_setup_habilita_hook_de_commit():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "git config core.hooksPath .githooks" in makefile
