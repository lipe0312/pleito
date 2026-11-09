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
| roles | `mainfilipe`, `aluno` | `pleito_owner`, `pleito_app_login`, `pleito_painel_login` |

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
python3 -c 'import secrets; print("POSTGRES_PANEL_PASSWORD=" + secrets.token_urlsafe(32))'
```

Copie cada linha inteira e substitua a linha correspondente no `.env`. Confirme que as tres
saem preenchidas, sem imprimir os valores, e que o arquivo esta fechado para outros usuarios:

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
| `POSTGRES_PANEL_PASSWORD` | idem | idem |
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
| `pleito_app` | coletor, gerador, aplicador, email, LLM | select e escrita por tabela/coluna; insert em auditoria |
| `pleito_painel` | painel | select e escrita limitada a configuracao, respostas, aprovacao e flags |
| `pleito_leitura` | consulta e metricas | apenas select |
| `pleito_chat` | chat de edicao (sem login ainda) | le `vaga` e `versao_curriculo`; insere versao de origem `chat`; nunca toca aprovacao nem candidatura |

Os quatro ultimos nao tem login (o do `pleito_chat` e a senha dele chegam com o item do chat).
`pleito_app_login` herda `pleito_app` e
`pleito_painel_login` herda `pleito_painel`; cada um recebe uma senha diferente. A migracao
`db/policies/0002_usuario_app.sql` configura a senha da aplicacao. O login do painel fica
inicialmente desabilitado; depois de aplicar as migracoes, ative-o com
`./scripts/rotacionar-senha.sh panel`.

O codigo abre conexoes de aplicacao e painel com credenciais distintas. A conexao recusa
qualquer destino diferente de `127.0.0.1:55432/pleito`. Grants especificam colunas de escrita,
nao ha permissao de delete para esses papeis e auditoria e append-only. O painel nao altera o
estado da vaga nem a prova de candidatura; a aplicacao nao altera flags nem cria aprovacoes.

A aplicacao grava vagas em `vaga` e cria empresas em `empresa` (so a coluna `nome`) pelo
repositorio de `src/coletor/repositorio.py`. A migracao `0003_vagas.sql` cria o indice unico
`vaga_unica_por_conteudo` (fonte, empresa e hash do conteudo) e as linhas de `fonte` dos
agregadores; `db/policies/0004_coletor.sql` concede o insert em `empresa`. A aplicacao continua
sem delete.

O modulo de email grava cada retorno em `evento_email` por `src/email/repositorio.py`, uma vez
por id de mensagem. A migracao `0004_evento_email_fila.sql` cria a coluna `fila` (`classificar`
ou `suspeito`; nula quando o evento foi aplicado) e o estado `oferta` em `estado_vaga`.
`db/policies/0006_evento_email.sql` concede o insert de `fila` a aplicacao e troca as policies
do evento: so a aplicacao marca `aplicado`, e so em evento autenticado e fora de fila. Cada
escrita (evento, mudanca de estado da vaga, evento aplicado) gera uma linha em `auditoria` com o
ator de `config/eventos_email.yaml`, que tambem define o estado de destino de cada etapa e de
quais estados a vaga pode sair.

`make testes-banco` roda testes de permissao negativos e a gravacao de vagas contra esse banco
depois de `make migrar`.
O alvo recusa conexao a qualquer porta que nao seja 55432, e os testes normais offline nao
conectam ao banco.

## Versoes de curriculo por vaga

`db/migrations/0005_versao_curriculo.sql` e `db/policies/0008_versao_curriculo.sql` (F5.1).

- `versao_curriculo` guarda vaga, numero, nivel, hash do PDF, versao do prompt, modelo, caminho em
  `dados/`, resultado das regras (`validacao`) e origem (`gerada`, `refeita`, `chat`). O numero e
  sequencial por vaga: repetir ou pular recusa a insercao.
- A versao e imutavel, inclusive para o dono do banco. So `nivel` e `protegida` mudam (campeoes,
  plano 7.9); nenhum papel de componente tem `UPDATE` nem `DELETE` nela.
- A uma pagina continua valendo por constraint (`versao_uma_pagina`) e por policy de insercao.
- Gerar uma versao nova invalida as aprovacoes da vaga ainda nao consumidas
  (`aprovacao.invalidada_em` e `invalidada_por_versao_id`, com linha em `auditoria` de ator
  `banco`) e, se a vaga estava `aprovada`, devolve para `aguardando_aprovacao`, mesmo com a
  aprovacao ja consumida: aquela versao deixou de ser a ultima e nao pode mais ser enviada.
  Aprovacao ja consumida fica como foi gravada (o token de uso unico foi gasto naquela versao
  exata), mas a candidatura so aceita a ultima versao da vaga: `candidatura_cria` (policy) e o
  trigger `candidatura_ultima_versao`, que trava a linha da vaga e recalcula "ultima" na mesma
  transacao, porque a policy usa o snapshot do inicio do comando e nao enxerga uma versao que
  acabou de dar commit.
- Gravar versao, criar candidatura, criar aprovacao e mudar `vaga.estado` se serializam por vaga
  (`SELECT ... FOR NO KEY UPDATE` na linha de `vaga`; o `UPDATE` de `vaga.estado` ja trava a
  propria linha). A ordem de lock e sempre `vaga` e depois `aprovacao`. Para isso a invalidacao
  feita pela versao nova pula (`FOR UPDATE SKIP LOCKED`) a aprovacao que alguem esta consumindo,
  em vez de esperar nela: esperar fecharia um ciclo com o envio, que consome a aprovacao e depois
  pede a `vaga` (deadlock `40P01`). A aprovacao pulada nao fica utilizavel: `aprovacao_consome`,
  a transicao para `aprovada` e a candidatura exigem a ultima versao, entao o envio concorrente e
  recusado com `check_violation` e o consumo dele desfeito junto. Duas versoes simultaneas nao
  repetem numero: a segunda espera e falha com `check_violation`, e quem grava tenta de novo.
- O painel so cria aprovacao para a ultima versao da vaga e com o hash dela
  (`aprovacao_cria` e o trigger `aprovacao_ultima_versao`, que trava a vaga); aprovacao invalidada nao pode ser consumida nem sustenta candidatura.
- Quem escreve versao: a aplicacao (gerador) com origem `gerada` ou `refeita`; o chat com origem
  `chat`, e so em vaga `aguardando_aprovacao` ou `aprovada` (`versao_escrita_chat`). O painel le e
  aprova; o chat nunca le nem escreve `aprovacao` e `candidatura`, e nao tem `INSERT` em
  `auditoria`: cada versao dele gera, por trigger do banco, a linha de ator `chat`.
- `historico_versao_curriculo` (view com `security_invoker`) lista as versoes de cada vaga com
  `aprovada` (aprovacao valida da ultima versao, ou de versao velha que chegou a ser enviada) e
  `enviada` (candidatura dela).
- `nivel` e `protegida` nao tem papel que atualize: hoje so o dono do banco muda, e o item dos
  campeoes (7.9) decide quem ganha esse grant.
- `caminho_pdf` e `hash_pdf` sao registro, nao prova do arquivo: quem consome a versao (aplicador,
  painel) deve calcular o hash do arquivo real em `dados/` e comparar com `hash_pdf` antes de
  mostrar ou enviar.
- `transicao_estado_vaga` e a maquina de estados do plano 4.11 no banco: um `UPDATE` de
  `vaga.estado` fora dela falha para qualquer papel. Estados de saida da vaga (`encerrada`) nao
  voltam. Alem do par origem/destino, `aprovada` exige aprovacao nao consumida, nao invalidada, nao
  expirada, da ultima versao e com o hash dela (consumida nao basta: a aplicacao nao refaz sozinha
  o ciclo `aprovada` e `aguardando_aprovacao`), e `aplicada_*` exige candidatura da vaga. O teste confere que toda transicao de `config/eventos_email.yaml` esta na tabela.

## O que o banco garante sozinho

Regras que nao dependem do codigo estar correto, porque vivem como constraint ou politica RLS.
Todas verificadas contra um Postgres 16 real:

- versao de curriculo com mais de uma pagina nao entra (`versao_uma_pagina`)
- uma candidatura por vaga (`candidatura_unica`)
- a mesma vaga da mesma fonte e empresa nao entra duas vezes, nem com outro `id_externo`
  (`vaga_unica_por_fonte` e `vaga_unica_por_conteudo`)
- nota fora de 0 a 100 e confianca fora de 0 a 1 nao entram
- evento de email com confianca 1.0 e remetente nao autenticado so entra em fila, e a fila
  `suspeito` so aceita evento do tipo `suspeito`, e vice-versa
  (`db/policies/0007_evento_email_fila_nao_autenticada.sql`)
- fila fora de `classificar` e `suspeito` nao entra (`evento_fila_valida`)
- evento nao autenticado ou em fila nunca e marcado como aplicado, e evento aplicado nao fica
  em fila (`evento_aplica` e `evento_aplicado_fora_da_fila`)
- linha de auditoria aceita insert e recusa update, inclusive para o papel de aplicacao
- token de aprovacao expirado ou ja consumido nao pode ser consumido de novo
- aprovacao invalidada por versao nova nao pode ser consumida (`aprovacao_consome`)
- transicao de estado fora da maquina do plano 4.11 falha (`vaga_transicao_de_estado`)

## Desligar

```bash
make banco-baixo
```

O servico do brew, e portanto a materia, continua no ar. Para conferir que o 5432 nunca foi
afetado:

```bash
psql -h 127.0.0.1 -p 5432 -d postgres -c '\l'
```
