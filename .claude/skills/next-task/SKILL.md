---
name: next-task
description: (Uso à parte; o fluxo padrão é a next-task-full.) Executa UM ciclo do pleito na sessão principal — escolhe o próximo item livre do backlog, planeja, implementa num worktree, valida e PARA para aprovação humana antes de commitar. Use só quando pedida pelo nome ("/next-task") ou por rotina agendada que a cite.
---

# Um ciclo: item → plano → código → gate → aprovação humana → PR

> **Uso à parte.** O fluxo padrão é a `next-task-full` (um comando, perguntas com recomendação, para só no "aprovado merge"). Esta skill vale quando pedida pelo nome: tudo na sessão principal, com parada antes do commit.

Repo `lipe0312/pleito`, base `main`, CLI `gh`. Regras em `CLAUDE.md`; fluxo em `docs/fluxo-de-desenvolvimento.md`. `ROOT` = primeira linha de `git worktree list --porcelain`.

## Fase 0 · Limpar
```bash
bash $ROOT/scripts/next-task-full/faxina.sh
```

## Fase 1 · Escolher (barato)
```bash
$ROOT/.venv/bin/python $ROOT/scripts/next-task-full/painel.py
```
Pegue o primeiro de LIVRES com `∥ ok`, sem `⛔decisao` (decisão → pergunte ao Filipe antes) e sem `schema` se houver MIGRATION ABERTA. Item manual (`M*`) nunca é escolhido. Nada sobrou → "backlog vazio — nada a fazer" e **pare**. Não invente tarefa.

## Fase 2 · Planejar
Skill `plan-issue`. Ela decide se o plano precisa de aprovação antes de codar.

## Fase 3 · Implementar
1. Worktree: na pasta principal → `EnterWorktree` com `name: feat-<N>`.
2. `git fetch -q origin && git checkout -q -b <feat|fix|chore|docs>/<N>-<slug> origin/main` e `bash $ROOT/scripts/next-task-full/preparar-worktree.sh`.
3. `gh issue edit <N> --add-label in-progress`.
- Só os critérios de aceite. Extra vira sugestão de item (`groom-issue`).
- Tela → **antes de editar**, screenshots 390 e 1280 com dados fictícios (o "antes" da `preview-aprovacao`) e skill `ui-build`. Texto visível → `mkt-copy`.
- Regra → teste antes. Segurança ou veredito → teste que falha sem a regra.
- Schema → migration nova em `db/migrations/`; `make migrar` só com o banco de pé e nenhuma outra migration aberta.
- Atualize a doc afetada e marque o item em `docs/plano-direcionado.md` (Andamento).
- Gate rápido: `.venv/bin/python -m pytest <arquivos> -q && .venv/bin/ruff check <arquivos>`.

## Fase 4 · Validar (tudo, uma vez, no fim)
`make testes && make lint`, e `make testes-banco` se o item toca banco e o banco está de pé.
Em paralelo (subagentes em background): `guarda-seguranca` no diff; `ui-reviewer` se houve tela; `copy-reviewer` se mudou texto visível. Corrija o que for **bloqueante**; polimento vira lista no PR.

## Fase 5 · Parar para o Filipe ⛔
**Não commite.** Skill `preview-aprovacao` (ou `n.a.` com motivo) e o resumo no formato da skill `ship`. Espere um "aprovado" explícito nesta sessão.

## Fase 6 · Entregar
Depois do "aprovado" → skill `ship` (commit sem assinatura, push da branch, PR com `Closes #N`). **Nunca faça merge** sem "aprovado merge". O preview fica em `.claude/preview/` até o merge.

## Bloqueios
Credencial, autorização interativa (OAuth), `sudo`, gasto real de LLM ou decisão de produto → proponha ao Filipe um item manual `M*` (skill `groom-issue`) ou o comentário na issue, e passe para o próximo item.
