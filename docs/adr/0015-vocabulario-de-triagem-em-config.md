# Vocabulário de triagem em configuração

## Status
Aceita

## Contexto
A ADR 0009 registrou os termos de classificação de função diretamente em
`viabilidade/triagem.py`. O spike confirmou a regra com vagas reais e testes, mas este
repositório exige que termos de busca e classificação sejam configuráveis sem alterar código.

## Decisão
Manter a lógica determinística de `inferir_funcao` e `extrair_anos_experiencia`, movendo para
`config/triagem.yaml` os termos por função, termos fora de escopo, siglas e termos genéricos.
Os limites de texto e de anos detectáveis também passam para a configuração. Os valores
iniciais preservam exatamente os termos e limites validados no spike. A mudança não altera
prioridade, normalização ou resultados esperados.

## Consequências
- alterações de vocabulário passam por revisão de configuração e testes, sem editar a regra
- o conjunto de testes do spike continua sendo a referência de comportamento
- termos novos precisam de cobertura para falsos positivos e falsos negativos
