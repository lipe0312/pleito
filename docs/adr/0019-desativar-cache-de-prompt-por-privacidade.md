# Desativar cache de prompt para proteger dados do currículo

## Status
Aceita

## Contexto
O roteador envia trechos do currículo e de vagas à Responses API. `store: false` impede o
armazenamento do estado da resposta, mas não desativa cache de prompt nem os logs de
monitoramento de abuso. Cache pode reduzir custo de entrada em requisições com prefixos
repetidos.

## Decisão
Priorizar a privacidade do currículo em vez da economia de tokens. Usar
`prompt_cache_options.mode: explicit` e não inserir breakpoints, o que desativa cache reads e
writes. O orçamento continua reservando o custo de entrada sem desconto de cache.

A documentação oficial confirma que o cache de prompt guarda tensores KV criptografados como
estado de aplicação e que o modo explícito sem breakpoints não grava nem reutiliza prefixos.
Isso não altera a retenção padrão de logs de monitoramento de abuso; `store: false` também não
os desativa.

## Referências

- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/api/docs/guides/your-data

## Consequências
- conteúdo do currículo não é enviado a cache writes de prompt
- prefixos repetidos não recebem desconto de tokens em cache
- o pedido precisa manter o modo explícito sem breakpoints

