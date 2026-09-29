# Celular descartado como servidor do pleito

## Status
Aceita

## Contexto
Q17 do plano previa servidor pessoal para quando o Mac estivesse desligado. Foi avaliado um
Motorola e22 (Android 12, 3,8 GB de RAM, sem limite de carga na bateria).

## Decisao
O pleito continua so no Mac. Fallback para Mac desligado e `pmset repeat wakeorpoweron`
mais `retry_ao_acordar`.

## Por que nao o celular
- Chromium e Playwright nao rodam de forma suportada em Android, e LaTeX e Docker tambem
  nao; o Mac teria que fazer o trabalho pesado de qualquer jeito
- 1,3 GB de RAM livre com o sistema ocioso
- dividir o banco entre dois aparelhos cria duas fontes de verdade; manter um so no Mac
  deixa o painel indisponivel com o Mac desligado de qualquer forma
- Android 12 tende a ficar sem patch de seguranca, e aparelho ligado o tempo todo sem limite
  de carga desgasta a bateria
- ganho de custo desprezivel: o gasto real e a chamada de LLM

## Consequencias
- notificacao e feita por email, ver 0013
- as informacoes do aparelho ficam em `~/Documents/celulares/moto_e22/` para uso futuro
  como monitor ou notificador, fora deste repositorio
