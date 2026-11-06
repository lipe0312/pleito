---
name: groom-issue
description: Transforma ideia, achado de revisão, pendência manual ou trecho do plano em item pronto do backlog do pleito — entrada em config/backlog.yaml (ficha com zona, dependências, toca, modelo, critérios testáveis) e a issue gerada a partir dela. Use para "cria issue", "quebra essa feature", "prepara o backlog", "isso vira item", "anota como manual".
---

# Ideia → item do backlog → issue

O backlog mora em `config/backlog.yaml` e é a fonte das issues. A issue nunca é escrita à mão para item do plano: ela sai do `scripts/next-task-full/criar_issues.py`, que põe as labels, as dependências com número e a linha `backlog: <id>` que o painel lê.

## 1. Conferir antes
- Duplicata: `gh issue list -R lipe0312/pleito --state all --search "<palavras>" --json number,title,state --limit 5` e `/usr/bin/grep -n "<palavra>" config/backlog.yaml`.
- Lugar no plano: `docs/plano-direcionado.md` (fase e objetivo) e, se precisar, a seção citada do `docs/PLANO.md`. Item que contradiz uma ADR → proponha ADR nova antes, não o item.

## 2. Escrever a ficha
Código (vai para `itens:`):
```yaml
  - id: F<fase>.<n>            # próximo livre da fase; 0 = repositório, M = monitor/fim
    fase: <n>                  # tem que existir em fases:
    titulo: <o que muda para quem usa, imperativo, sem acento>
    zona: <uma zona existente ou nova; duas frentes da mesma zona nunca rodam juntas>
    depende: [<ids>]           # item de código ou manual M*
    schema: <true se cria migration>
    toca: [<credencial|terceiro|banco|llm|custo|latex|dado-pessoal|ui|regra|seguranca|config>]
    modelo: <opus-high|sonnet-high|sonnet-medium|haiku-medium>
    criterios:
      - <comportamento verificável, com arquivo ou comando>
      - <regra de segurança ou de veredito → "com teste que falha sem ela">
    fora: <o que fica para outro item>
    decisao: <pergunta de produto com a opção recomendada primeiro, se houver>
    nota: <restrição de dependência ou de custo, se houver>
```
Manual (vai para `manuais:`), quando só o Filipe pode fazer (credencial, consentimento OAuth, `sudo`, gasto real, aprovação humana, configuração de conta externa):
```yaml
  - id: M<n>
    titulo: <ação, imperativo>
    depende: [<ids>]
    como:
      - <passo com o comando exato>
    pronto: <como conferir que ficou feito, por comando>
    porque: <o que fica travado sem isso>
```
Regras:
- Maior que 2 dias de trabalho → quebre em itens encadeados por `depende`.
- Título sem código de planejamento e sem nome de pessoa; critérios sem email, telefone ou trecho do currículo.
- Escolha do `modelo`: tabela da §3 da `next-task-full`.

## 3. Mostrar e esperar
Mostre a ficha e **espere aprovação** antes de gravar e de criar a issue (escrever em issue é ação externa).

## 4. Gravar e gerar
1. Edite `config/backlog.yaml` e rode `.venv/bin/python -m pytest tests/test_backlog_painel.py -q` (dependência inexistente, ciclo e campo faltando quebram aqui).
2. `.venv/bin/python scripts/next-task-full/criar_issues.py` (dry) e, aprovado, `--aplicar`.
3. A mudança do `config/backlog.yaml` entra num PR (nunca commit direto na `main`); junto do item que a originou, se houver.
4. Corpo da issue desatualizado depois de mudar a ficha → `criar_issues.py --reescrever <id> --aplicar`.

Labels que o script põe: `ready`, `fase:<n>`, `area:<zona>`, `decisao` (tem `decisao:`), `seguranca` (toca credencial ou segurança) e `manual` nos M*. `blocked` só à mão, quando falta algo que o backlog não representa.
