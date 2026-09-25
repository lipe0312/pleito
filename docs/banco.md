# Banco e acesso pelo pgAdmin

## Por que um cluster separado

A maquina ja tem PostgreSQL 18 nativo (Homebrew) escutando em `127.0.0.1:5432`, com o banco
`MATA_60_2026_2` e a role `aluno`, usados na disciplina de banco de dados.

O pleito **nao entra nesse cluster**. Ele roda em um container proprio, em `127.0.0.1:55432`,
com volume de dado, roles e configuracao separados. Motivos:

- um `DROP`, um `ALTER ROLE` ou um restore errado no pleito nao alcanca a materia
- as politicas de RLS e os papeis do pleito nao aparecem no cluster da disciplina
- parar o pleito e `docker compose down`, sem tocar no servico do brew
- versoes independentes: a materia segue no 18, o pleito no 16

O pgAdmin 4 instalado como app do Mac gerencia os dois, cada um como um server registrado
diferente. O container de pgAdmin existe no compose mas fica desligado por profile, porque o
app nativo torna ele desnecessario.

| | materia | pleito |
| --- | --- | --- |
| servidor | PostgreSQL 18 nativo (brew) | PostgreSQL 16 em Docker |
| host e porta | 127.0.0.1:5432 | 127.0.0.1:55432 |
| sobe com | `brew services` (ja ativo) | `make banco` |
| banco | `MATA_60_2026_2` | `pleito` |
| roles | `mainfilipe`, `aluno` | `pleito_owner`, `pleito_app_login` |

## Passo 1: ir para a pasta e criar o .env

```bash
cd ~/Documents/PESSOAL/DOCUMENTOS/Curriculos/pleito
cp .env.example .env
chmod 600 .env
```

## Passo 2: gerar as senhas

Nunca escolha senha a mao e nunca digite senha direto no terminal, porque o comando fica no
`~/.zsh_history`. Gere e escreva no `.env`:

```bash
python3 -c 'import secrets; print("POSTGRES_PASSWORD=" + secrets.token_urlsafe(32))'
python3 -c 'import secrets; print("POSTGRES_APP_PASSWORD=" + secrets.token_urlsafe(32))'
```

Copie cada linha inteira e substitua a linha correspondente no `.env`. Confirme que as duas
saem preenchidas, sem imprimir o valor, e que o arquivo esta fechado para outros usuarios:

```bash
awk -F= '/^POSTGRES_(APP_)?PASSWORD=/{print $1 "=" length($2) " chars"}' .env
ls -l .env
```

`secrets.token_urlsafe(32)` gera 43 caracteres com 256 bits de entropia, no alfabeto
`A-Za-z0-9_-`. Nao ha o que reforcar nisso: e mais forte que qualquer senha escolhida a mao, e
o alfabeto sem aspas nem barra evita problema de escape em `.pgpass`, em URL de conexao e em
SQL.

### Nao use `grep` para ler a senha

No shell deste projeto `grep` e uma funcao injetada pelo hook do rtk, que resume a saida em vez
de imprimir a linha. Um `grep ... | cut -d= -f2- | pbcopy` copia vazio, porque o `cut` recebe o
resumo e nao a linha. Use `awk`, `/usr/bin/grep` ou, melhor, os alvos do Makefile abaixo. A
regra vale para qualquer pipeline onde a saida de `grep` alimenta outro comando.

`PGADMIN_EMAIL` e `PGADMIN_PASSWORD` sao usados apenas pelo container de pgAdmin. Usando o app
nativo, pode deixar os dois em branco.

## Passo 3: subir o banco e aplicar a modelagem

```bash
make banco
make banco-status
make migrar
```

`make banco` sobe apenas o servico `postgres`. `make banco-status` imprime banco, usuario e
versao, e serve para confirmar que voce esta falando com o cluster do pleito e nao com o da
materia. `make migrar` aplica `db/migrations/` e depois `db/policies/`.

## Passo 4: copiar a senha sem ela aparecer na tela

```bash
make senha-banco
```

Copia `POSTGRES_PASSWORD` para a area de transferencia e imprime apenas a contagem de
caracteres. `make senha-app` faz o mesmo para a senha da aplicacao. Nenhum dos dois escreve a
senha no terminal nem no historico do shell.

## Passo 5: registrar os dois servidores no pgAdmin

Abra o pgAdmin 4 pelo Launchpad. Na primeira vez ele pede uma master password, que protege as
senhas guardadas dentro do proprio pgAdmin. Gere uma e guarde no seu gerenciador de senhas:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'
```

### Servidor da materia

Botao direito em Servers, Register, Server.

- aba **General**, Name: `MATA 60 - materia`
- aba **Connection**:
  - Host name/address: `127.0.0.1`
  - Port: `5432`
  - Maintenance database: `postgres`
  - Username: `mainfilipe`
  - Password: em branco (o cluster local aceita conexao local sem senha), Save password desmarcado
- Save

### Servidor do pleito

Botao direito em Servers, Register, Server.

- aba **General**, Name: `pleito - docker`
- aba **Connection**:
  - Host name/address: `127.0.0.1`
  - Port: `55432`
  - Maintenance database: valor de `POSTGRES_DB` no `.env`, ou seja `pleito`
  - Username: valor de `POSTGRES_USER`, ou seja `pleito_owner`
  - Password: valor de `POSTGRES_PASSWORD` do `.env`, com **Save password** marcado
- Save

Host `127.0.0.1` e porta `55432` porque o app do pgAdmin roda no Mac e entra pela porta que o
container publica. A porta `5432` que aparece dentro do `docker-compose.yml` e a porta interna
do container e nao serve aqui. Essa distincao so importaria se voce usasse o pgAdmin em
container, onde o host passaria a ser `postgres` e a porta `5432`.

Depois de salvar, o schema do pleito fica em `pleito - docker > Databases > pleito > Schemas >
pleito`. As tabelas nao aparecem em `public`, porque a migracao cria um schema proprio.

## Passo 6 (opcional): psql sem digitar senha

Para usar `psql` direto do Mac contra o container sem repetir a senha, use `~/.pgpass`, que e o
mecanismo do proprio Postgres e evita a senha no historico do shell:

```bash
umask 077
printf '127.0.0.1:55432:pleito:pleito_owner:COLE_A_SENHA_AQUI\n' >> ~/.pgpass
chmod 600 ~/.pgpass
psql -h 127.0.0.1 -p 55432 -U pleito_owner -d pleito
```

Edite o arquivo num editor para colar a senha, em vez de digitar o `printf` com ela inline,
senao a senha vai para o historico.

Alternativa sem `.pgpass`, que entra pelo container e nao pede senha nenhuma:

```bash
make psql
```

## Rotacionar senha

Se uma senha vazar, se aparecer num log ou por higiene periodica:

```bash
make senha-rotacionar          # owner
./scripts/rotacionar-senha.sh app
```

O script gera uma senha nova, aplica o `ALTER ROLE`, atualiza a linha do `.env`, refaz o
`chmod 600` e deixa a nova na area de transferencia. Depois disso, atualize a senha salva no
pgAdmin e no `~/.pgpass`, se voce usa.

A senha nunca vai por argumento de linha de comando: o `ALTER ROLE` entra por stdin do `psql`,
porque argumento de processo aparece em `ps` para qualquer usuario da maquina. Verificado: apos
a rotacao a senha nova autentica e a antiga passa a ser recusada.

## Onde cada senha vive

| senha | onde fica | protegida por |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | `.env`, fora do git, `chmod 600` | permissao de arquivo |
| `POSTGRES_APP_PASSWORD` | idem | idem |
| a mesma, para o psql | `~/.pgpass`, `chmod 600` | permissao de arquivo |
| a mesma, no pgAdmin | store interno do pgAdmin | master password do pgAdmin |
| master password do pgAdmin | seu gerenciador de senhas | fora da maquina |
| token do Gmail (fase 1) | Keychain do macOS | login do Mac |

Regras: senha nunca em arquivo versionado, nem em exemplo; nunca em `export` no terminal, para
nao cair no historico; nunca reaproveitada entre o cluster da materia e o do pleito.

## Papeis do pleito

| papel | para que serve | pode |
| --- | --- | --- |
| `pleito_owner` | migracoes e pgAdmin | tudo dentro do banco `pleito` |
| `pleito_app` | coletor, gerador, aplicador, email | select, insert, update; insert em auditoria |
| `pleito_painel` | painel | o mesmo, mais criar aprovacao e mexer em flag |
| `pleito_leitura` | consulta e metricas | apenas select |

Os tres ultimos nao tem login. `pleito_app_login` herda `pleito_app` e e o unico com senha,
aplicada por `db/policies/0002_usuario_app.sql`.

## O que o banco garante sozinho

Regras que nao dependem do codigo estar correto, porque vivem como constraint ou politica RLS.
Todas verificadas contra um Postgres 16 real:

- versao de curriculo com mais de uma pagina nao entra (`versao_uma_pagina`)
- uma candidatura por vaga (`candidatura_unica`)
- nota fora de 0 a 100 e confianca fora de 0 a 1 nao entram
- evento de email com confianca 1.0 e remetente nao autenticado e recusado pela RLS
- linha de auditoria aceita insert e recusa update, inclusive para o papel de aplicacao
- token de aprovacao expirado ou ja consumido nao pode ser consumido de novo

## Desligar

```bash
make banco-baixo
```

O servico do brew, e portanto a materia, continua no ar. Para conferir que o 5432 nunca foi
afetado:

```bash
psql -h 127.0.0.1 -p 5432 -d postgres -c '\l'
```
