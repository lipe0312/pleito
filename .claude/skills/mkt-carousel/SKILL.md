---
name: mkt-carousel
description: Cria carrosséis de LinkedIn sobre o pleito como projeto de portfólio (como foi construído, decisões de arquitetura, segurança, o que o spike provou) — roteiro slide a slide e PNGs 1080×1350 renderizados localmente com HTML e o Playwright do .venv, custo zero. Publicação sempre manual. Use para "carrossel", "post sobre o projeto", "conteúdo para o LinkedIn".
---

# Carrossel (roteiro → slides → PNG)

O LinkedIn **nunca** é automatizado (CLAUDE.md, plano 10.7): esta skill entrega arquivos; quem publica é o Filipe, pelo app. Para o texto do post e a capa, combine com `linkedin-agent:li-carousel` e passe tudo por `linkedin-agent:li-human`.

## 1. Roteiro (sempre)
- 6 a 8 slides. Slide 1 = gancho com um fato real do projeto ("2484 vagas coletadas, 303 passaram no funil"). Último = um CTA único (ver o repositório).
- Uma ideia por slide, ≤ 25 palavras. Regras da skill `mkt-copy`.
- Fontes permitidas: `docs/estado.md`, `docs/viabilidade.md`, `docs/adr/`, `docs/seguranca.md`. Número só se estiver num desses arquivos.
- Público: recrutador e engenheiro. Não misture com conselho de carreira genérico.
- Entregue o roteiro em tabela e **espere aprovação** antes de gerar imagens.

## 2. Gerar (local, padrão)
Escreva `<scratchpad>/carrossel-<slug>/slides.html` (um `<section id="sN">` 1080×1350 por slide, tokens de `docs/painel-design.md`, fonte do sistema, sem fonte remota) e exporte com o Playwright do `.venv`:
```bash
$ROOT/.venv/bin/python -I - <<'EOF'
from pathlib import Path
from playwright.sync_api import sync_playwright
pasta = Path("<scratchpad>/carrossel-<slug>")
with sync_playwright() as p:
    pagina = p.chromium.launch().new_page(viewport={"width": 1080, "height": 1350})
    pagina.goto((pasta / "slides.html").as_uri())
    for indice, slide in enumerate(pagina.locator("section").all(), start=1):
        slide.screenshot(path=str(pasta / f"{indice:02d}.png"))
EOF
```
Canva só pela skill `mkt-canva`, se o Filipe pedir edição posterior por lá.

## 3. Conferir
Abra os PNGs (Read): texto ≥ 40 px, contraste AA, nada cortado (margem 80 px).
Proibido no slide: email, telefone, print do Gmail, print do painel com vaga ou currículo real, nome de recrutador ou empresa que respondeu, token, custo real de API.
Saída: pasta dos PNGs (fora do repositório) + legenda (≤ 150 palavras, 3 a 5 hashtags específicas, CTA).
