# Segredos em .env local, repositorio publico

## Status
Aceita

## Contexto
O repositorio e publico. O sistema lida com senha de banco, token do Gmail, chave de API de
modelo, perfil de navegador autenticado e PDF com telefone pessoal.

## Decisao
- `.env` fora do git, com `.env.example` versionado sem um unico valor real
- `dados/` e `segredos/` no `.gitignore`, incluindo o perfil do Playwright
- senhas geradas com `secrets.token_urlsafe(32)`, nunca escolhidas a mao
- o sistema nunca guarda nem digita senha de plataforma de vaga: o login e manual, feito
  pelo Filipe uma vez no perfil persistente do navegador
- credencial de longo prazo (token do Gmail) migra para o Keychain do macOS quando a fase 1
  comecar; o `.env` cobre apenas o spike
- PDF gerado nunca entra no git, mesmo o do baseline

## Consequencias
- clonar o repositorio nao da acesso a nada
- trocar de maquina exige refazer `.env` e o login manual do navegador
- um `git add -f` em `dados/` ou `segredos/` e o unico caminho para vazamento; vale um hook
  de pre-commit quando as constraints do `.claude` forem definidas
