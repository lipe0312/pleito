---
name: handoff
description: Compactação certeira do pleito — grava em 15 linhas o estado da tarefa (item, decisões, arquivos, próximo passo, gate) antes de /compact, /clear ou troca de sessão, para retomar sem reler o repo. Use ao fim de cada fase longa ou quando o contexto passar de ~60%.
---

# Handoff antes de compactar

Escreva em `.claude/handoff/<N>-<slug>.md` (pasta no `.gitignore`; `<N>` é a issue) e sobrescreva, não acumule:

```markdown
# <branch> — <id do backlog> #<N> <título>
Worktree: <caminho absoluto> · PR: #<pr> | sem PR
Fase: plano | implementação | validação | aguardando aprovação
Decidido: bullets curtos, inclusive o que o Filipe aprovou e as respostas das rodadas
Feito: arquivos tocados + estado (ok / pela metade)
Falta: próximo passo concreto (comando ou arquivo:linha)
Armadilhas: o que já falhou e por quê
Gate: último resultado de make testes, make lint, make testes-banco
Manual do Filipe: M* liberados ou criados por esta entrega
```

Nunca escreva no handoff: conteúdo de `.env`, `segredos/`, `dados/`, token, email ou telefone, trecho do currículo.

Depois sugira ao Filipe o comando certo:
- mesma tarefa, contexto cheio → `/compact foco: <id> #<N>, decisões e próximo passo; descarte logs de teste e leituras de arquivo`
- tarefa nova → `/clear` (o handoff fica no disco)
- retomar → "leia `.claude/handoff/<N>-<slug>.md` e continue"

A limpeza do "aprovado merge" (§11 da `next-task-full`) apaga o handoff da issue.
