# LLM por chave de API da OpenAI, chave no .env

## Status
Aceita. Substitui a escolha de provedor da 0006; o roteador por tier continua valendo.

## Contexto
Q2 do plano: assinatura em modo nao interativo ou chave de API. O Filipe tem creditos na
OpenAI e quer custo previsivel.

## Decisao
- provedor inicial: OpenAI por chave de API, com `config/modelos.yaml` mapeando tier para
  modelo. Verificados em 2026-09-28 na documentacao oficial: `gpt-6-luna` para o tier rapido
  (US$ 0,10 entrada e US$ 0,50 saida por milhao de tokens) e `gpt-6-sol` para o tier forte
  (US$ 2,00 entrada e US$ 10,00 saida por milhao). Ambos suportam Responses API, saida
  estruturada e esforco de raciocinio `low`. Os dois ficam desabilitados ate passar pelo
  conjunto de avaliacao. A ADR 0017 define os controles de ativacao, registro e orcamento
- o modelo so entra em uso depois de passar no conjunto de avaliacao (secao 8.6 do plano)
- a chave fica no `.env`, fora do git. Nao vai para o banco: o dump, o backup e o pgAdmin
  passariam a carregar a chave, e o banco precisaria de outra credencial para chegar nela
- controle de gasto: o sistema soma o custo de cada chamada no registro de uso e desconta do
  saldo inicial informado em `config/limites.yaml`. A ADR 0018 define o fallback seletivo de
  pontuacao final para o tier rapido abaixo de `llm.saldo_minimo_forte_usd`; escrita e chat
  continuam adiados. Teto diario ou mensal sempre bloqueia a chamada, sem fallback
- o saldo e local porque a API nao expoe o credito prepago de forma confiavel; a reconciliacao
  com o painel da OpenAI e manual
- o orcamento e mensal (`llm.orcamento_mensal_usd`), nao diario. O teto do dia e o menor entre
  `orcamento_usd_dia_max` e o restante do mes dividido pelos dias que faltam; o que sobra de
  um dia rola para o seguinte, e o que estoura para
- LLM so depois de tudo que e deterministico. Ordem do funil, e cada etapa so recebe o que
  sobrou da anterior:
  1. duplicata (hash da vaga) e vaga ja vista: zero chamada
  2. filtros de funcao, senioridade, anos exigidos, localizacao e empresa: zero chamada
  3. tier rapido pre-pontua no maximo `vagas_pre_pontuadas_max`, com a descricao cortada em
     `descricao_max_chars`, e o resultado fica em cache pelo hash do texto
  4. tier forte so recebe vaga com pre-nota de pelo menos `pre_nota_minima_para_forte`, e
     gera variante para as vagas que passaram, ate `variantes_geradas_max` (8, como no plano) por dia
- dia sem vaga que passe da pre-nota minima: nenhuma chamada forte, nenhuma variante. O
  resumo por email sai dizendo que nao houve vaga boa, sem completar a lista com vaga ruim
- prefixo fixo do prompt (regras, inventario) vem primeiro por estabilidade do contexto, mas
  os cache writes permanecem desativados por privacidade, conforme a ADR 0019. O esforco de
  raciocinio fica em `config/modelos.yaml`; `low` foi confirmado para os dois candidatos na
  documentacao oficial e continua sujeito a avaliacao
- estimativas por vaga aguardam o conjunto de avaliacao e medidas de tokens de prompts reais.
  Registrar uso real nao substitui a reserva previa do custo maximo; a ADR 0017 define esse
  controle e impede chamadas concorrentes de exceder o orcamento
- credencial de longo prazo migra para o Keychain conforme a 0008

## Verificacao oficial

- modelos: https://developers.openai.com/api/docs/models/gpt-6-luna e
  https://developers.openai.com/api/docs/models/gpt-6-sol
- precos: https://developers.openai.com/api/docs/pricing
- saida estruturada: https://developers.openai.com/api/docs/guides/structured-outputs
- esforco de raciocinio: https://developers.openai.com/api/docs/guides/reasoning

## Por que nao Claude por assinatura
- termos e limites da assinatura para uso automatizado nao foram verificados, e o projeto
  nao constroi em cima de regra que nao leu
- assinatura tem cota compartilhada com o uso interativo do Filipe; a API tem custo por
  token, medivel e limitado pelo `llm.orcamento_mensal_usd` de `config/limites.yaml`
- trocar de volta e mudar o YAML, entao a decisao nao trava nada

## Consequencias
- `config/modelos.yaml` deixa de apontar `provedor_padrao: claude`
- nomes, precos e capacidades verificados ficam registrados na configuracao, mas nenhum tier
  e habilitado antes de concluir a avaliacao
- rever valores na documentacao oficial sempre que um modelo for trocado
