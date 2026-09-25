# Provedor unico no inicio, roteador por tier pronto para trocar

## Status
Aceita

## Contexto
Q2, Q21 e Q22 do plano. O Filipe ja paga Claude e tem conta OpenAI. O custo precisa ser
minimo e as versoes de modelo mudam rapido.

## Decisao
Um unico ponto de acesso em `src/llm/`, com `config/modelos.yaml` mapeando etapa para tier
e tier para modelo de cada provedor. Comeca com Claude apenas: tier rapido para extracao,
classificacao de email, pre-pontuacao e mapeamento de campos; tier forte apenas para
pontuacao final, escrita de slots, chat de edicao e revisao cruzada.

Trocar provedor ou modelo e mudar o YAML, e passa obrigatoriamente pelo conjunto de
avaliacao da secao 8.6 do plano antes de entrar em uso.

## Consequencias
- menos superficie de exposicao de dado pessoal: um provedor
- aplicador e triagem deterministica nao chamam LLM nenhuma
- o roteador precisa existir desde a fase 0, mesmo com um provedor so
