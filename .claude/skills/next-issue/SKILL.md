---
name: next-issue
description: Mapa curto do backlog do pleito em ondas — o que entra agora, o que roda em paralelo sem conflito de zona nem de migration, o que espera o quê, e os manuais do Filipe. Só lê, não muda nada. Use para "/next-issue", "quais as próximas issues", "o que roda em paralelo", "ordem do backlog".
---

# next-issue: o que entra agora e o que roda junto

Só leitura. Não põe label, não cria branch, não abre worktree. Para executar um item do mapa, o fluxo é a `next-task-full`.

## Passo único
```bash
ROOT="$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')"
$ROOT/.venv/bin/python $ROOT/scripts/next-task-full/painel.py --ondas              # até 3 frentes por onda
$ROOT/.venv/bin/python $ROOT/scripts/next-task-full/painel.py --ondas --frentes 2
$ROOT/.venv/bin/python $ROOT/scripts/next-task-full/painel.py --json               # tudo, inclusive ondas
```

O script aplica as regras do repositório (lógica em `scripts/next-task-full/backlog.py`, testada em `tests/test_backlog_painel.py`):
- **Dependência:** o `depende:` do `config/backlog.yaml`. Concluído é issue fechada como concluída; `not_planned` não conta. Item que espera um em andamento vai para a onda seguinte.
- **Migration:** `schema: true`. No máximo uma por onda, contando a que já está aberta (o banco é um só e compartilhado).
- **Zona:** o `zona:` do item. Duas frentes da mesma zona nunca ficam na mesma onda.
- **Em andamento:** PR aberto, worktree `feat-N` ou label `in-progress`. Ocupa frente e zona da onda 1.
- **Ordem:** fase, depois id.
- **Manual:** item `M*` nunca entra em onda. Aparece em MANUAIS DO FILIPE quando liberado; item que depende de manual pendente cai em SEM ONDA.

## Resposta (curta, ≤ 15 linhas)
```
Agora (paralelo): F0.1 #13 · F1.5 #15 · F1.8 #16
Depois: F0.2 #14 ⛔decisão (←F0.1) · F1.6 #17 (←F1.8) · F1.7 #18 (←F1.5)
Depois: …
Manuais do Filipe agora: M1 #38 · M2 #39 · M3 #40
Atenção: <só o que o script não vê, ex.: duas da mesma onda mexem no mesmo arquivo>
Rodar: claude --permission-mode bypassPermissions -n "F0.1" "/next-task-full F0.1 --rec"
```
- Uma linha por onda, com `(←id)` quando o item espera alguém.
- Dê as linhas `claude …` só para a onda 1, e nunca com `--rec` para item `⛔decisao` (a decisão se pergunta numa sessão com rodada: `/next-task-full F0.2`).
- Antes de responder, confira com bom senso: a zona é uma heurística. Se souber que duas da onda 1 tocam o mesmo arquivo (`config/limites.yaml`, `pyproject.toml`, `Makefile`), diga em "Atenção" e não corrija o script na hora.
- Item em SEM ONDA → diga o motivo (quase sempre um manual pendente).

## Quando ajustar
Zona nova nasce na ficha do item (skill `groom-issue`). Regra nova de paralelismo → mude `backlog.py` e o teste no mesmo PR.
