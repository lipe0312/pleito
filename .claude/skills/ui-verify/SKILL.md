---
name: ui-verify
description: Abre o painel local do pleito num navegador de verdade (Playwright do .venv, ou Claude in Chrome) e confere o que o agente fez — screenshots 390 e 1280, erros de console, requisições, acessibilidade, CSP e escape de texto externo — sempre com dados fictícios. Use depois de mudar qualquer tela ou para depurar bug visual.
---

# Verificar o painel no navegador

## Pré-requisito: dados fictícios, nunca os reais
O banco do Filipe tem vagas, eventos de email e currículo reais. **Não** tire screenshot do painel ligado nele.
- **Padrão:** render pelo `TestClient` com o repositório falso dos testes, servido ao Playwright pelo próprio app (script da §2 da skill `preview-aprovacao`). Não sobe servidor, não abre porta.
- **Com interação HTMX de verdade:** `make painel-ficticio` no worktree (criado pelo F1.6: repositório fictício de `tests/fixtures`, sem banco). Antes do F1.6, só rotas que não leem banco com `make painel`. Porta de `config/painel.yaml`, sempre `127.0.0.1`.

## Roteiro por rota
1. Abra a rota em **1280×800** e em **390×844**; salve `.claude/screenshots/<N>-<rota>-<largura>.png` (pasta no `.gitignore`).
2. Console: qualquer erro, inclusive violação de CSP = **Quebrado**.
3. Requisições: só `127.0.0.1`. Qualquer outra origem (CDN, fonte, imagem remota) = **Quebrado**. 4xx/5xx inesperado = **Quebrado**.
4. Acessibilidade: `page.accessibility.snapshot()` (Playwright) ou `read_page` (Chrome): botão sem nome, campo sem rótulo, ordem de foco, foco visível.
5. Escape: carregue uma vaga fictícia com título `<img src=x onerror=alert(1)>` e confira que aparece como texto.
6. Ação que escreve: sem token CSRF tem que falhar; com confirmação, só depois de confirmar.
7. Interaja com o fluxo principal (aprovar, rejeitar com motivo, filtrar) e repita 1 a 3 nas telas resultantes.

## Claude in Chrome (opcional)
Carregue as ferramentas numa chamada só (`ToolSearch` com `select:` das `mcp__claude-in-chrome__*`), comece por `tabs_context_mcp` e abra aba nova. Nunca dispare `alert`/`confirm` do navegador: use a confirmação em HTML da própria tela. Nunca navegue para Gmail, LinkedIn, Gupy ou plataforma de vaga daqui.

## Economia de tokens
Prefira a árvore de acessibilidade (texto) para checar estrutura; screenshot só nas duas larguras. Filtre a lista de rede por origem ≠ `127.0.0.1` e status ≥ 400.

## Saída
Quebrado (bloqueia) · Polimento (≤ 5) · caminhos dos screenshots.
