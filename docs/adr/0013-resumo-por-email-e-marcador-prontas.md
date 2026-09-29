# Resumo diario por email e marcador Candidaturas/Prontas

## Status
Aceita

## Contexto
Q10 e Q11 do plano. O Filipe quer o material pronto e o aviso no email antes das 8h, com
push no iPhone sem infraestrutura nova.

## Decisao
- o sistema envia um email de resumo para um unico destinatario, lido de `PLEITO_EMAIL_DESTINO`
  no `.env` (o repositorio e publico, entao o endereco nunca entra em arquivo versionado),
  com assunto fixo para filtro
- o email recebe o marcador `Candidaturas/Prontas`; o app do Gmail no iPhone notifica por
  marcador, sem servidor de push
- entrega antes das 8h; `config/limites.yaml` guarda os horarios (hoje descoberta 06:30 e
  resumo 07:45), com mais de uma janela para o Mac, sem impedir o uso dele
- escopos do Gmail: ler, alterar marcadores e enviar. O envio e o unico acrescimo ao plano
  e so aceita esse destinatario unico. Exclusao, lixeira, encaminhamento e resposta continuam
  proibidos por lint
- o monitor de disponibilidade e o ultimo passo, logico: le o registro de execucao e avisa
  por email se uma janela nao gerou resumo. Nao dispara retry

## Consequencias
- o plano previa marcadores por etapa, e `Prontas` entra antes de `Aplicadas`
- o escopo de envio precisa ser aprovado no projeto OAuth do Google Cloud
