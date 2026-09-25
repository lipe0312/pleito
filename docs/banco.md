# Banco e acesso pelo pgAdmin

## Subir

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Rode o gerador quatro vezes e preencha no `.env`: `POSTGRES_PASSWORD`, `POSTGRES_APP_PASSWORD`,
`PGADMIN_PASSWORD` e, quando for testar envio real, `PLEITO_EGRESS_TOKEN_SUBMIT_REAL`.
Nenhuma senha e escolhida a mao e nenhuma tem valor padrao no repositorio.

```bash
make banco
make migrar
```

Postgres fica em `127.0.0.1:55432`, pgAdmin em `http://127.0.0.1:55050`. As portas sao altas
de proposito, para nao colidir com um Postgres instalado direto no Mac, e o bind em
`127.0.0.1` garante que nada disso escuta na rede local.

## Registrar o servidor no pgAdmin

Isso e manual e se faz uma unica vez. Nao da para fazer pelo terminal sem escrever a senha
num arquivo de import, e por isso a escolha foi digitar no pgAdmin.

1. abra `http://127.0.0.1:55050` e entre com `PGADMIN_EMAIL` e `PGADMIN_PASSWORD`
2. botao direito em Servers, Register, Server
3. aba General, Name: `pleito local`
4. aba Connection:
   - Host: `postgres` (o nome do servico no compose, porque o pgAdmin fala com o Postgres
     pela rede interna do Docker, nao pelo localhost do Mac)
   - Port: `5432` (a porta interna, nao a 55432 publicada)
   - Maintenance database: valor de `POSTGRES_DB`
   - Username: valor de `POSTGRES_USER`
   - Password: valor de `POSTGRES_PASSWORD`, marque Save password
5. Save

A senha fica no volume `pgadmin-data`, cifrada com a senha de login do pgAdmin, fora do git.

Se preferir um cliente no proprio Mac (DBeaver, TablePlus, psql), ai o host e `127.0.0.1` e a
porta e `55432`, porque a conexao entra pela porta publicada.

## Acesso pelo terminal

```bash
make psql
```

## Papeis

| papel | para que serve | pode |
| --- | --- | --- |
| `POSTGRES_USER` (owner) | migracoes e pgAdmin | tudo |
| `pleito_app` | coletor, gerador, aplicador, email | select, insert, update; insert em auditoria |
| `pleito_painel` | painel | o mesmo, mais criar aprovacao e mexer em flag |
| `pleito_leitura` | consulta e metricas | apenas select |

Nenhum dos tres papeis de aplicacao tem login proprio: `pleito_app_login` herda `pleito_app`
e e o unico com senha, aplicada por `db/policies/0002_usuario_app.sql`.

## O que o banco garante sozinho

Regras que nao dependem do codigo estar correto, porque vivem como constraint ou politica RLS:

- versao de curriculo com mais de uma pagina nao entra (`versao_uma_pagina`)
- token de aprovacao expirado ou ja consumido nao pode ser consumido de novo
- evento de email com confianca 1.0 e remetente nao autenticado nao entra
- resposta do banco de respostas so e lida depois de aprovada
- linha de auditoria nunca e alterada nem apagada por quem escreve nela
- uma candidatura por vaga (`candidatura_unica`)
