---
name: mkt-canva
description: Gera peças visuais do pleito como projeto de portfólio no Canva via MCP — imagem de prévia social do repositório no GitHub, banner do README, capa do LinkedIn, one-pager do projeto — sem nenhum dado pessoal do currículo. Use para material visual que o Filipe vai editar depois no Canva.
---

# Peças no Canva

Pré-requisito: MCP `canva` autenticado na conta do Filipe (`/mcp` → canva → OAuth, feito por ele). Sem o MCP, use o caminho local da `mkt-carousel` (HTML + Playwright) e diga isso. Cada chamada ao Canva pede aprovação.

## Peças padrão
| Peça | Formato | Regras |
|---|---|---|
| Prévia social do repositório | 1280×640 PNG | nome "pleito", uma linha do que faz, sem print de dado real; sobe à mão em Settings → Social preview |
| Banner do README | 1600×400 | mesma linha; contraste AA; fica em `docs/` só se o Filipe aprovar versionar |
| Capa do LinkedIn | 1584×396 | sem texto atrás da foto de perfil (canto inferior esquerdo) |
| One-pager do projeto | A4 PDF | problema → como funciona (fluxo de `docs/fluxos.md`) → segurança → stack; números só de `docs/estado.md` |
| Carrossel | 1080×1350 | use `mkt-carousel` |

## Fluxo
1. Texto pela skill `mkt-copy`; aprove com o Filipe.
2. Crie no Canva com as cores de `docs/painel-design.md`.
3. Exporte (PNG para digital, PDF para impressão) e informe o link do design.

## Nunca no Canva
O currículo, o PDF gerado, os blocos, o guia de adaptação, print do Gmail ou do painel com dado real, email, telefone, endereço. O Canva é terceiro: só entra o que poderia estar no README público. Nenhum logo de empresa ou plataforma de vaga.
