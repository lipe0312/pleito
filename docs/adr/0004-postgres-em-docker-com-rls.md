# Postgres 16 em Docker com RLS e pgAdmin local

## Status
Aceita

## Contexto
Q4 do plano. O sistema guarda dado pessoal (telefone no PDF, historico de candidatura,
conteudo de email) e o plano exige papeis com RLS. O Filipe quer acessar pelo pgAdmin.

## Decisao
`postgres:16-alpine` e `dpage/pgadmin4` via docker compose, ambos publicados **apenas em
127.0.0.1**, em portas altas (55432 e 55050) para nao colidir com instalacao local.
Autenticacao `scram-sha-256`. Tres papeis sem login (`pleito_app`, `pleito_leitura`,
`pleito_painel`) e um papel de login que herda `pleito_app`.

RLS ativa em vaga, versao_curriculo, aprovacao, candidatura, evento_email, flag_sistema e
resposta_banco. As politicas carregam regra de negocio que o codigo nao pode contornar:

- `versao_curriculo` so aceita insert com `paginas = 1`
- `aprovacao` so pode ser consumida se ainda nao consumida e nao expirada
- `evento_email` so aceita insert autenticado ou com confianca abaixo de 1.0
- `resposta_banco` so e legivel depois de aprovada
- `auditoria` aceita insert, nunca update nem delete

## Consequencias
- a regra de uma pagina passa a ser garantida por constraint, nao so por validador
- o banco nunca escuta em interface externa
- pgAdmin em `SERVER_MODE=False` guarda a conexao no volume; a senha do Postgres vai no
  `.env`, fora do git, e e digitada uma vez no pgAdmin
