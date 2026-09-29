# Registrar e limitar atomicamente o uso do roteador LLM

## Status
Aceita

## Contexto
A ADR 0012 define OpenAI por API, armazenamento da chave no `.env`, avaliação obrigatória e
limites mensal e diário. Ainda não há roteador implementado, registro de versão de prompt e
validação, nem garantia de que chamadas concorrentes respeitem o teto em conjunto. A
documentação oficial consultada em 2026-09-28 confirma GPT-6 Luna e Sol, preços por tokens,
Responses API, saída estruturada e esforço `low`; a avaliação do projeto ainda está pendente.

## Decisão
O roteador é o único módulo autorizado a chamar provedores. Cada solicitação valida a saída
contra schema estrito, não habilita ferramentas e registra tarefa, tier, provedor, modelo,
versão do prompt, tokens, custo e resultado da validação. A chave permanece fora do banco e
dos logs. As chamadas Responses definem `store: false`; isso impede persistir estado de
aplicação, mas não desliga os logs de monitoramento de abuso previstos pela política da OpenAI.
O cache de prompt usa modo explícito sem breakpoints, para impedir gravação e reuso de prefixos
com dados do currículo.

Cada tier permanece desabilitado até ter modelo e avaliação aprovados. A aprovação registra
identificador do modelo, data e versão do conjunto de avaliação. Um modelo sem esses dados não
pode gerar chamada, mesmo que a chave esteja configurada.

O custo máximo da chamada é reservado atomicamente no banco antes de enviar dados ao provedor,
usando o tamanho máximo configurado do prompt, a sobrecarga de tokens, o máximo de tokens de
saída e os preços verificados. Uma trava transacional serializa reservas concorrentes. O limite
efetivo do dia é o menor entre `orcamento_usd_dia_max` e o saldo mensal restante dividido pelos
dias restantes do mês. Ao atingir qualquer teto, a chamada não ocorre. Para o tier forte,
saldo mensal abaixo de `saldo_minimo_forte_usd` adia a tarefa, sem rebaixar o tier. Após
resposta, a reserva é reconciliada com o custo calculado a partir dos tokens; falhas liberam a
reserva e permanecem registradas sem conteúdo pessoal.

Os valores verificados em 2026-09-28 são: GPT-6 Luna, entrada US$ 0,10 e saída US$ 0,50 por
milhão de tokens; GPT-6 Sol, entrada US$ 2,00 e saída US$ 10,00 por milhão. Ambos suportam
Responses API, saída estruturada, esforço `low`, janela de contexto de 1.050.000 tokens,
entrada máxima de 922.000 e saída máxima de 128.000. A configuração impõe limites menores por
chamada e mantém ambos desabilitados até a avaliação da seção 8.6.

Referências oficiais consultadas:

- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://developers.openai.com/api/docs/models/gpt-6-sol
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/reasoning
- https://developers.openai.com/api/docs/guides/your-data
- https://developers.openai.com/api/docs/guides/prompt-caching

## Consequências
- gastos concorrentes não podem ultrapassar o saldo permitido por uma verificação seguida de
  chamadas paralelas
- erro de rede ou orçamento insuficiente adia a tarefa, sem fallback silencioso
- valores de preço e capacidade têm fonte e data de verificação antes de qualquer ativação
- chamadas reais ficam bloqueadas enquanto modelo, preço ou avaliação estiverem pendentes
