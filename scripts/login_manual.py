"""Abre o perfil persistente do Playwright para login manual. Nao fecha sozinho."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viabilidade.config import ambiente

env = ambiente()
env.egress_perfil.mkdir(parents=True, exist_ok=True)

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://portal.gupy.io/en"

with sync_playwright() as p:
    contexto = p.chromium.launch_persistent_context(
        user_data_dir=str(env.egress_perfil),
        headless=False,
        accept_downloads=False,
        user_agent=env.user_agent,
    )
    pagina = contexto.new_page()
    pagina.goto(url)
    print(f"Janela aberta em {url}")
    print("Faca login manualmente. Feche a janela do navegador quando terminar.")
    print("A sessao fica salva em", env.egress_perfil)
    contexto.wait_for_event("close", timeout=0)
