# Postgres 16 em Docker com RLS e pgAdmin local

## Status
Aceita

## Contexto
Q4 do plano. O sistema guarda dado pessoal (telefone no PDF, historico de candidatura,
conteudo de email) e o plano exige papeis com RLS. O Filipe quer acessar pelo pgAdmin.

A maquina ja tem PostgreSQL 18 nativo do Homebrew em `127.0.0.1:5432`, com o banco
`MATA_60_2026_2` e a role `aluno`, em uso na disciplina de banco de dados. E ja tem pgAdmin 4
instalado como app do macOS.

## Decisao
`postgres:16-alpine` em container proprio, publicado **apenas em 127.0.0.1**, na porta 55432.
O cluster da disciplina no 5432 nao e reaproveitado: cluster, volume, roles e versao do pleito
sao separados, para que nenhuma migracao, restore ou `ALTER ROLE` do projeto alcance a materia.

O pgAdmin usado e o app nativo do macOS, que registra os dois servidores como entradas
distintas, ambos em `127.0.0.1` e distinguidos pela porta. O servico `pgadmin` do compose fica
atras do profile `pgadmin-container` e nao sobe no `make banco`, porque o app nativo o dispensa
e evita a confusao de host interno (`postgres:5432`) contra host publicado (`127.0.0.1:55432`).

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
- a disciplina fica intocada: `make banco-baixo` nao afeta o servico do brew
- custo de um container Postgres a mais rodando junto do cluster nativo
- a senha do Postgres vai no `.env`, fora do git com `chmod 600`, e e digitada uma vez no
  pgAdmin, que a guarda cifrada pela sua master password
