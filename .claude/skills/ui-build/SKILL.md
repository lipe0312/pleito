---
name: ui-build
description: OBRIGATÓRIA para qualquer tela, componente ou mudança visível no painel local do pleito (FastAPI + HTMX em 127.0.0.1) e no HTML do email de resumo. Orquestra docs/painel-design.md → padrões que já existem em src/painel → direção visual → implementação segura (escape, CSP, CSRF, sem CDN) → verificação com ui-verify → web-design-guidelines.
---

# Construir tela do painel (pipeline obrigatório)

Pule um passo só se ele não se aplica, e diga qual e por quê.

## 1. Contexto de design (≤ 2 min)
- Leia `docs/painel-design.md`: tokens, densidade, estados, anti-padrões. Tela que pede algo que ele não cobre → skill `ui-design-references` antes de inventar.
- Superfície: **Painel** (desktop, denso, um usuário, revisão rápida do dia) · **Email de resumo** (lido no iPhone, HTML simples, sem imagem remota) · **Preview** (só aprovação, fora do git).
- O painel é ferramenta de trabalho de uma pessoa: dado real na tela (vaga, nota, motivo, etapa, gasto), nada de marketing.

## 2. Reusar antes de criar
1. `src/painel/templates/` e `src/painel/static/`: o que já existe. Uma base de layout, parciais por bloco.
2. HTMX local (`src/painel/static/htmx.min.js`, SHA-256 fixo nos testes) para trocar pedaço da página. **Nunca** CDN, fonte remota, framework JS, Node.js ou build de front (ADR 0005).
3. Componente novo só se não houver equivalente; nasce no `docs/painel-design.md` no mesmo PR.

## 3. Direção visual
Hierarquia por tipografia e espaço, números tabulares em nota e gasto, uma cor de marca e as semânticas (ok, atenção, erro, suspeito). Nada de gradiente, glassmorphism, emoji como ícone, sombra pesada, texto centralizado em tudo. `docs/painel-design.md` vence em conflito.

## 4. Implementar (segurança é parte da tela)
- Jinja com autoescape ligado; texto de vaga, de email e de LLM é **sempre** texto, nunca `|safe`, nunca `innerHTML` (ameaça XSS do plano 10.5).
- Sem script inline e sem `style` inline que a CSP do item F1.8 bloqueie; JS só em arquivo de `static/`.
- Toda ação que escreve é `POST` com token CSRF; ação irreversível (aprovar envio, autorizar submit real, rejeitar) pede confirmação explícita na própria tela.
- O painel lê com o papel do painel e escreve só as colunas da ADR 0016; nunca abre conexão com outro papel.
- Link externo de vaga abre com `rel="noopener noreferrer"`; link vindo de email nunca vira link clicável (phishing, plano 10.1).
- Textos em pt-BR pela skill `mkt-copy`.
- Desktop primeiro (1280), mas legível em 390. Alvo de clique ≥ 32 px, foco visível, contraste AA.
- Estado vazio, carregando e erro: os três. Dia sem vaga boa diz isso (ADR 0013).
- Teste no `tests/test_painel_*.py` com `TestClient`: rota responde, texto malicioso sai escapado, POST sem CSRF é recusado.

## 5. Ver de verdade
Delegue ao subagente `ui-reviewer` (skill `ui-verify`) com as rotas tocadas. Corrija tudo o que ele marcar como **Quebrado**.

## 6. Conferência final
Skill **web-design-guidelines** nos arquivos tocados. Corrija acessibilidade e foco; o resto vai para "polimento" no PR.

Entrega: screenshots antes e depois no resumo da skill `ship` e no preview.
