---
name: plan-issue
description: Fase de plano de um item do pleito — explora com subagente barato e escreve um plano curto com "o que o Filipe passa a ver", arquivos, riscos de segurança e custo, e testes. Use antes de codar qualquer item, issue ou feature.
---

# Planejar um item (≤ 1 tela)

1. Leia a ficha: `gh issue view <N> -R lipe0312/pleito --json title,body,labels,comments` (o corpo traz critérios, fora do escopo, dependências e a linha `backlog: <id>`). Decisão em comentário mais novo vence o corpo.
2. Delegue a localização ao subagente `explorer` (haiku): onde a mudança entra, o arquivo parecido a imitar, o módulo do spike em `viabilidade/` a migrar, a seção do `docs/PLANO.md` e as ADRs. **Não** leia arquivo grande no contexto principal.
3. Escreva o plano neste formato, sem passar de ~30 linhas:

```markdown
## Plano — <id> #N <título>
**O Filipe passa a ver:** <1 frase: o que muda no Gmail, no painel, no email de resumo ou no terminal>
**Como conferir:** <comando ou tela, antes → depois>
**Critérios de aceite:** (copiados da issue)
**Arquivos:** caminho — o que muda (máx. 8)
**Config:** chaves novas em config/*.yaml ou .env.example (sem valor real)
**Riscos:** segredo · Gmail (envio, exclusão, escopo) · egress (dry-run) · LLM (injeção, schema, custo) · LaTeX · banco (grants, RLS, auditoria) · dado pessoal
**Testes:** regra (escrito antes) · ataque (injeção, LaTeX malicioso, remetente forjado, SQL em campo) · banco · nenhum com rede
**Paralelizável?** sim/não — zona e migration (painel `--ondas`)
**Fora do escopo:** …
```

4. **Precisa de aprovação antes de codar** (entre em plan mode ou espere "ok") se qualquer um:
   - cria migration ou muda grant, RLS ou policy
   - toca credencial, OAuth, Keychain, envio de email ou egress
   - pode gastar LLM real ou muda orçamento, tier ou `habilitado`
   - cria tela nova ou muda layout de tela existente
   - contradiz ADR ou o `docs/plano-direcionado.md`
   Caso contrário, siga direto e mostre o plano junto do resultado.

Seja específico. "Melhorar o funil" não é plano; "vaga com pre_nota abaixo de `pre_nota_minima_para_forte` nunca chega ao tier forte, provado por teste com `uso_llm` vazio" é.
