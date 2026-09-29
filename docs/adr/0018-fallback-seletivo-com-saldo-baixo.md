# Fallback seletivo para pontuação com saldo baixo

## Status
Aceita

## Contexto
A ADR 0012 descrevia fallback geral para o tier rápido abaixo do saldo mínimo do tier forte,
enquanto a ADR 0017 adiava toda tarefa forte sem rebaixamento. A regra do plano proíbe
rebaixamento para escrita, mas pontuação e classificação podem usar o modelo rápido.

## Decisão
Quando o saldo mensal fica abaixo de `llm.saldo_minimo_forte_usd`, `pontuacao_final` pode ser
reservada e executada no tier rápido. A classificação de email já pertence ao tier rápido e
permanece nele. Escrita de slots e chat de edição são adiados; nunca usam fallback.

O conjunto de tarefas elegíveis fica explícito em `config/modelos.yaml`. O roteador só tenta o
fallback ao receber a exceção específica de saldo mínimo do tier forte. Falta de orçamento
diário, teto mensal ou qualquer outra falha não provoca fallback. O tier rápido também precisa
estar habilitado e aprovado no seu conjunto de avaliação.

## Consequências
- pontuação final continua disponível com saldo mensal abaixo do mínimo do tier forte
- escrita e chat preservam o tier e aguardam saldo suficiente
- limites diário e mensal continuam sendo bloqueios duros
- testes cobrem o fallback permitido, as tarefas adiadas e o bloqueio sem fallback por teto

