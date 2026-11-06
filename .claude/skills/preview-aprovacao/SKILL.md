---
name: preview-aprovacao
description: Gera um HTML único, offline e fora do git, que mostra ao Filipe o que a entrega muda. Simplificado (padrão) — resumo didático em HTML/CSS com "como era → como fica", 3 casos e critérios, sem subir nada; completo — antes × depois com screenshots reais do painel com dados fictícios e o render real da tela pelo TestClient (+ mini simulador se for regra de triagem ou de veredito). Use antes de todo pedido de aprovação ("aprovado merge" na next-task-full e no prompt-for-next-task, commit na next-task e na feature) e apague antes do merge.
---

# Preview para aprovação (só olhar e aprovar)

Objetivo: o Filipe decide **sem rodar nada**. Um arquivo que abre no navegador do Mac.

## 0. Onde e quando
- Arquivo: `.claude/preview/<N>-<slug>.html` (pasta no `.gitignore`: **nunca** entra em commit). No completo, as imagens de `.claude/screenshots/` são embutidas em base64; no simplificado entram por caminho relativo, opcionais.
- Gere logo antes do portão (§9 da `next-task-full`, Fase 5 da `next-task`, passo 5 da `feature`, ⛔2 do `prompt-for-next-task`). Pediu "ajustes" → refaça, não apague.
- No "aprovado merge" ou quando o PR fecha: `rm -f .claude/preview/<N>-*.html`.

## 1. Nível
- **Simplificado (padrão):** modelo em `.claude/skills/next-task-full/references/preview-simples.html`. "Como era → como fica" **desenhado em HTML/CSS** só do pedaço que muda (com o novo marcado), 3 casos "situação → o que acontece" (comum, borda, ataque ou erro, tirados dos testes), tabela critério × feito e a linha de gate e riscos. Sem tela → "Como funciona" em 3 passos e "o que fica bloqueado". Sem JS, sem base64, sem subir o painel. Até ~80 linhas.
- **Completo:** só quando escolhido (rodada 2 da `next-task-full`, `--preview completo`, "preview completo"). Seções 2 e 3.

## 1b. Tipo (1 linha no resumo)
| A entrega… | Preview |
|---|---|
| tela nova ou mudança visível no painel | **A · Visual**: antes × depois + estado final |
| regra de triagem, pontuação, classificação de email, orçamento, validador | **B · Simulador** + explicação |
| Gmail, OAuth, egress, LLM, banco, segurança, agendamento | **C · Explicação** (fluxo com o que é bloqueado) |
| docs, chore, config | nenhum → `Preview: n.a. (<motivo>)` |
Misto (regra + tela) → A com uma seção do B.

## 2. Coletar — só no completo
- **Dados:** sempre fictícios. Nunca suba o painel apontando para o banco com vagas e currículo reais para tirar foto. Monte o contexto da tela com os mesmos objetos que os testes usam (fixtures em `tests/fixtures/`) e renderize pelo `fastapi.testclient.TestClient`.
- **Antes:** screenshots 390 e 1280 **antes de mexer no código**. Esqueceu? Renderize a mesma rota num worktree de `origin/main` no scratchpad (`git worktree add <scratchpad>/antes origin/main`, rode o script abaixo de lá com o `.venv` do checkout principal, depois `git worktree remove --force`). Schema mudou → "antes indisponível", descrito pelo diff.
- **Depois:** reaproveite os screenshots do `ui-reviewer`. Sem eles, use o Playwright Python que já está no `.venv` (nunca instale navegador novo):
  ```python
  # <scratchpad>/snap.py — rode do worktree: $ROOT/.venv/bin/python -I <scratchpad>/snap.py <rota> <saida>
  import sys
  sys.path.insert(0, ".")
  from fastapi.testclient import TestClient
  from playwright.sync_api import sync_playwright
  from src.painel.app import app
  rota, saida = sys.argv[1], sys.argv[2]
  BASE = "http://127.0.0.1"
  cliente = TestClient(app, base_url=BASE)
  def responder(r):
      if not r.request.url.startswith(BASE + "/"):
          return r.abort()
      resposta = cliente.request(r.request.method, r.request.url[len(BASE):])
      r.fulfill(status=resposta.status_code, headers=dict(resposta.headers), body=resposta.content)
  with sync_playwright() as p:
      navegador = p.chromium.launch()
      for largura in (390, 1280):
          pagina = navegador.new_page(viewport={"width": largura, "height": 900})
          pagina.route("**/*", responder)
          pagina.goto(BASE + rota)
          pagina.screenshot(path=f"{saida}-{largura}.png", full_page=True)
      open(f"{saida}.html", "w", encoding="utf-8").write(pagina.content())
      navegador.close()
  ```
  Tudo o que não é o painel é abortado: o snap não sai da máquina, e o CSS e o HTMX locais vêm do próprio app. Tela que depende de banco → injete o repositório falso do teste antes do `TestClient` (mesmo padrão de `tests/test_painel_local.py`).
- **Código (B e C):** trechos **reais** do diff (≤ 15 linhas cada, com `arquivo:linha`). Nada de pseudocódigo.

## 3. Montar o HTML — só no completo (≤ ~400 linhas sem contar o base64, sem CDN)
Monte com um script no scratchpad que lê as imagens e o snap e injeta no modelo (nunca base64 à mão). Tokens de `docs/painel-design.md` em `:root`, texto pt-BR, mobile first.
1. **Topo:** título · "O Filipe passa a ver: …" · item, issue, PR, branch · selo "Dados fictícios".
2. **A · Visual:** antes × depois lado a lado (empilha no celular), alternador 390/1280, até 4 notas numeradas na margem; estado final em `<iframe srcdoc sandbox>` com o HTML do snap.
3. **B · Simulador:** porte a função pura para JS **linha a linha** (mostre o original ao lado), com os mesmos limites de `config/` e 3 exemplos que batem com os testes.
4. **C · Explicação:** "O problema", "Como funciona agora" (diagrama SVG inline ou passos numerados), "O que fica bloqueado" (envio a outro destino, exclusão de email, chamada forte sem pré-nota, submit sem token).
5. **Rodapé:** critério × onde conferir e a pergunta do portão ("aprovado merge / ajustes").

Proibido: qualquer coisa de `dados/` ou `segredos/`, currículo real, email, telefone ou endereço do Filipe, token, custo real de API, número inventado, promessa que o diff não cumpre.

## 4. Entregar
- `open <arquivo>` no Mac.
- No resumo da `ship`: `**Preview:** .claude/preview/<arquivo>.html (tipo A/B/C)` ou `Preview: n.a. (<motivo>)`.
- Antes de qualquer commit: `git diff --cached --name-only | /usr/bin/grep -q '^\.claude/preview/' && echo "ERRO: preview no commit"` → tire do stage.
