# Python 3.11 com FastAPI e HTMX no painel

## Status
Aceita

## Contexto
Q3 do plano pedia o caminho mais leve, mantendo manutenibilidade e migracao facil se crescer.

## Decisao
Python 3.11 em todo o sistema, FastAPI com templates e HTMX no painel. Sem build de
frontend, sem node no caminho critico. A camada de dominio fica fora do modulo do painel,
entao trocar HTMX por React depois e reescrever so a borda de apresentacao.

## Consequencias
- um unico runtime para coletor, gerador, validador, aplicador, email e painel
- Playwright e pdflatex integram direto, sem ponte entre linguagens
- interatividade rica (drag-and-drop, editor complexo) fica limitada; se virar requisito,
  a migracao e uma decisao nova, nao um retrabalho de dominio
