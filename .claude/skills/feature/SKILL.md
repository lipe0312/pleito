---
name: feature
description: Fluxo direto, SEM subagentes, para implementar no pleito uma mudança descrita em linguagem de produto — planeja, implementa num worktree, revisa com as skills certas para o tipo de mudança e entrega um resumo. Roda do começo ao fim sem paradas intermediárias. Use quando o Filipe descrever algo com "o que quero / como imagino / o que espero no final", ou disser "/feature". O fluxo padrão para itens do backlog continua sendo a next-task-full.
---

# Feature direta: planejar → implementar → revisar → entregar

Tudo na sessão principal, sem subagentes, mas **sempre num worktree** (ADR 0022). Ambiguidade pequena → escolha o mais simples coerente com `docs/plano-direcionado.md` e registre no resumo, sem perguntar. Regras de código em `CLAUDE.md`.

## Entrada esperada
- **Feature:** o que é
- **Visão:** como o Filipe imagina a tela, o email ou o comportamento
- **Resultado esperado:** como ele vai saber que ficou pronto
- **Ao final:** `parar para aprovação` (padrão) ou `commitar e abrir PR`

## 1. Classificar (1 linha)
Se a feature é um item do `config/backlog.yaml`, use a ficha dele (zona, toca, modelo, critérios) e a issue que já existe. Senão marque o que ela toca:

| Toca… | Obrigatório |
|---|---|
| tela do painel | skill `ui-build` (dentro dela: `ui-design-references` se não houver padrão em `docs/painel-design.md`, `ui-verify`, `web-design-guidelines`) |
| texto que o Filipe ou um recrutador lê (painel, email de resumo, resposta padrão, rascunho) | skill `mkt-copy` (+ `mkt-cta` se houver ação principal) |
| regra de triagem, veredito, classificação, orçamento | teste **antes** da implementação, que falha sem a regra |
| Gmail, OAuth, Keychain, egress, LLM, LaTeX, banco | checklist nível 1 da `sec-predeploy`, aplicado por você ao diff com a lista do agente `guarda-seguranca` |
| schema | migration nova em `db/migrations/`, nunca editar aplicada; `make migrar` e `make testes-banco` com o banco de pé |

## 2. Planejar (≤ 20 linhas, mostre e siga sem esperar)
Leia só o necessário (Grep + Read com offset; `docs/PLANO.md` só na seção citada). Escreva:
```
O Filipe passa a ver: …
Como conferir: comando ou tela (http://127.0.0.1:<porta de config/painel.yaml>)
Arquivos: …
Skills que vou usar: …
Riscos: segredo · Gmail · egress · LLM e custo · LaTeX · banco
Fora do escopo: …
```
Worktree e branch: na pasta principal → `EnterWorktree` com `name: feat-<slug>`; depois `git fetch -q origin && git checkout -q -b feat/<slug> origin/main` e `bash $ROOT/scripts/next-task-full/preparar-worktree.sh` (`ROOT` = primeira linha de `git worktree list --porcelain`).

## 3. Implementar
- Vai mudar tela → antes de editar, screenshots 390 e 1280 da rota em `.claude/screenshots/` com dados fictícios (o "antes" do preview; skill `ui-verify`).
- Siga as skills do passo 1 na ordem da tabela. Regra → teste primeiro.
- Sem rede real e sem LLM real: `respx` e o roteador com cliente falso. Egress só `dry_run`.
- Gate rápido ao fim de cada parte: `.venv/bin/python -m pytest <arquivos> -q && .venv/bin/ruff check <arquivos>`.

## 4. Revisar (você mesmo, com as skills)
1. Tela → `ui-verify` completo + `web-design-guidelines` nos arquivos tocados. Corrija o que estiver quebrado ou sem acessibilidade.
2. Texto → releia com as regras da `mkt-copy`. Nada de número, experiência ou tecnologia inventada.
3. Diff → checklist do agente `guarda-seguranca` (`.claude/agents/guarda-seguranca.md`), item por item.
4. Gate completo: `make testes && make lint`, e `make testes-banco` se o banco estiver de pé. Falhou → corrija e rode de novo.

## 5. Entregar
Skill `preview-aprovacao` (HTML fora do git). Depois o resumo no formato da skill `ship` (O Filipe passa a ver · Como conferir · Antes → depois · Skills usadas · Riscos · Gate · Escolhas feitas sem perguntar).
- `parar para aprovação` → pare aqui.
- `commitar e abrir PR` → skill `ship` §2 (commit sem assinatura, push da branch, PR com `Closes #N` se houver issue). Merge só com "aprovado merge" do Filipe nesta sessão.

## Armadilhas conhecidas
- Saída cortada pelo `rtk` → `rtk proxy <cmd>` ou a ferramenta Read; em pipe use `/usr/bin/grep`.
- Nunca leia `.env`, `segredos/`, `dados/` nem o Keychain; use só os caminhos.
- O worktree nasce da `origin/main`: o `.venv` e o `.env` chegam por symlink do `preparar-worktree.sh`.
