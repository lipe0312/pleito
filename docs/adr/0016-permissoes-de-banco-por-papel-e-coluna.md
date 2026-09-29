# Restringir escritas no banco por papel e coluna

## Status
Aceita

## Contexto
A migration inicial concede `SELECT`, `INSERT` e `UPDATE` em todas as tabelas aos papéis de
aplicação e painel. As policies RLS cobrem sete tabelas, mas não impedem que o painel escreva
em outras tabelas sem RLS, e grants amplos permitem alterar colunas de controle que não são
necessárias para cada componente.

## Decisão
Revogar grants amplos e conceder operações explicitamente por papel e tabela. Escritas de
coluna ficam limitadas ao conjunto necessário para cada componente. A aplicação não altera
flags nem cria aprovações; o painel pode alterar somente o valor e o motivo da flag, além de
criar aprovações. A aplicação pode consumir aprovação e registrar prova de candidatura. Os
dois papéis podem inserir auditoria, nunca atualizá-la ou apagá-la. Logins separados herdam
apenas o papel de componente correspondente.

Preservar RLS nas tabelas sensíveis e garantir que privilégios SQL e policies RLS concordem.
Testes negativos consultam os privilégios efetivos no PostgreSQL isolado do projeto e tentam
operações proibidas. Esses testes só podem conectar a `127.0.0.1:55432`, no banco `pleito`;
nunca usam o cluster da disciplina na porta 5432.

## Consequências
- painel e rotinas não compartilham credencial de login
- cada nova operação de escrita exige grant e policy explícitos e um teste de permissão
- pgAdmin e migrations continuam usando somente o papel owner
