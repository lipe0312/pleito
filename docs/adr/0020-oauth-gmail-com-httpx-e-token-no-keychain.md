# OAuth do Gmail com httpx puro e refresh token no Keychain

## Status
Aceita

## Contexto
A Fase 1 precisa ler e rotular o Gmail do Filipe sem guardar credencial em arquivo (ADR 0008).
As bibliotecas oficiais do Google (`google-auth-oauthlib`, `google-api-python-client`) trazem
dependências grandes para um uso pequeno: um fluxo de autorização e quatro chamadas REST.
O repositório é público e o cliente OAuth é do tipo Desktop.

## Decisão
- fluxo OAuth Desktop com redirect para loopback (`127.0.0.1`, porta livre) e PKCE S256,
  feito com `httpx`, `http.server` e `secrets`, sem dependência nova
- `state` aleatório por execução, comparado em tempo constante; callback com `state` ausente,
  repetido ou diferente é recusado antes de trocar o código
- escopos vêm de `config/emails.yaml`, mas só passam se estiverem na allowlist do código
  (`gmail.readonly`, `gmail.modify`, `gmail.labels`); o mesmo vale para os escopos que o
  Google devolve na troca do código. Hoje o pedido é só `gmail.modify`
- só o `refresh_token` é persistido, no Keychain do macOS, pelo binário `security` em caminho
  absoluto. A gravação usa `security -i` e manda `add-generic-password -U -s ... -a ... -w ...`
  pelo stdin, então o valor nunca aparece na lista de processos. O valor vai entre aspas
  duplas e é recusado se tiver aspas, barra invertida, espaço ou caractere de controle, o que
  impede quebrar ou encadear comandos no parser do `security`. Depois de gravar, o valor é
  lido de volta com `find-generic-password -w` para confirmar a gravação, porque o modo
  interativo não garante código de saída por comando
- o `access_token` vive só na memória: é renovado no início de cada execução e de novo, uma
  vez, num 401. Se o Google rotacionar o `refresh_token`, o novo é regravado
- o cliente expõe só `listar`, `ler`, `rotular` e `arquivar`; o identificador da mensagem é
  validado para não alterar o caminho da chamada
- um teste de arquitetura varre `src/` e recusa `delete`, `trash`, `forward`, `send` e rotas
  equivalentes fora do módulo de resumo, cujo nome vem de `config/emails.yaml`

## Consequências
- nenhuma dependência nova; o fluxo é pequeno o bastante para ser testado offline com `respx`
- a autorização é manual, uma vez, por `make gmail-autorizar`
- o envio do resumo (Fase 1.5) vai exigir `gmail.send` na allowlist e uma nova autorização,
  decisão registrada quando aquele item for feito
- trocar de Mac exige autorizar de novo, porque o token não sai do Keychain
