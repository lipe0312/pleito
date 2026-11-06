# Envio do resumo diário por messages.send, conferido antes de sair e em dry-run por padrão

## Status
Aceita

## Contexto
A ADR 0013 decidiu que o resumo vai para um único destinatário lido de `PLEITO_EMAIL_DESTINO` e
recebe o marcador `Candidaturas/Prontas`. Faltava decidir como o envio acontece sem abrir a
porta para mandar email a outra pessoa e sem dar capacidade de envio ao cliente Gmail comum.

## Decisão
- o envio mora só em `src/email/resumo.py` (`gmail.modulo_resumo` em `config/emails.yaml`).
  `ClienteResumo` herda o `ClienteGmail`, que continua sem nenhum método de envio; o teste de
  arquitetura prova que esse é o único arquivo de `src/` com `/send`, e que ele não exclui nem
  encaminha
- a mensagem é MIME texto puro (`email.message.EmailMessage`, política SMTP), enviada em `raw`
  base64url para `messages/send`. Assunto, rótulo e frases vêm de `config/resumo.yaml`
- o destino é relido do ambiente no momento do envio, nunca recebido do chamador. Só passa um
  endereço simples, sem nome, vírgula, ponto e vírgula nem quebra de linha. Antes de sair, a
  mensagem já serializada é relida: exatamente um `To` igual ao destino e nenhum `Cc`, `Bcc` ou
  `Resent-*`. Assunto vazio ou com quebra de linha é recusado ao carregar a configuração
- o id de `Candidaturas/Prontas` é resolvido antes do envio; sem o rótulo na conta, nada sai.
  Depois do envio, o rótulo entra por `messages/{id}/modify`, porque `messages.send` ignora
  `labelIds`
- `make resumo` roda em dry-run: monta e mostra assunto e corpo, sem Keychain e sem rede. O
  envio real exige `--enviar` explícito. A mensagem de erro não repete o valor recusado

## Consequências
- o rótulo cai na cópia da conta autorizada; se o destino for outra conta, a notificação por
  marcador do iPhone não acontece. O destino esperado é a própria conta do Filipe
- `messages.send` precisa de `gmail.modify` ou `gmail.send`; hoje `gmail.modify` já cobre
- a contagem de vagas prontas chega por `--prontas`; ligá-la ao banco é trabalho da fase 4
