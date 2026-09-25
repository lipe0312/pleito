# Onde estamos

Atualizado em 2026-09-24. Este arquivo e o registro corrente do projeto: o que foi feito, o que
foi verificado de verdade e o que vem depois. `docs/viabilidade.md` guarda o veredito por
fronteira, gerado por comando.

## Resumo em uma linha

Fundacao pronta e verificada. Baseline do curriculo fechou GO. Banco modelado, isolado e com as
invariantes provadas. As duas fronteiras externas, ingest e egress, seguem **nao testadas**, e
por isso `sistema_ativo` continua desligada.

## Estado por frente

| Frente | Estado | Evidencia |
| --- | --- | --- |
| repositorio | publico, 3 commits | github.com/lipe0312/pleito |
| modulo de viabilidade | escrito, 73 testes passando, ruff limpo | `make testes`, `make lint` |
| baseline do curriculo | **GO** em pt e en, 1 pagina, 0 overfull | `cli baseline` |
| banco | 14 tabelas, 7 com RLS, 3 migracoes aplicadas | `make banco-status` |
| isolamento do cluster | zero roles `pleito*` no 5432 da disciplina | consulta ao cluster nativo |
| ingest | **nao testado**, nenhuma fonte contatada | - |
| egress | **nao testado**, nenhum formulario aberto | - |
| EDA | sem dado, depende do ingest | - |
| veredito global | **nao testado** | `docs/viabilidade.md` |

## O que foi feito

**Decisao de ordem.** O roteiro do plano coloca trazer vagas na fase 4 e enviar candidatura na
fase 6, depois de seis fases erguidas sobre premissa nao testada. Invertemos: um modulo
`viabilidade/` isolado ataca as duas fronteiras externas primeiro e emite GO por fonte e por
plataforma. ADR 0002.

**Modulo de viabilidade.** Ingest com Greenhouse, Lever e Ashby por API publica, e Gupy e
Solides como investigacao. Egress em Playwright com perfil persistente e dry-run que para antes
do submit. Baseline que extrai os dois curriculos do guia, corrige e valida compilacao. EDA de
completude, duplicidade e elegibilidade. Veredito que consolida as tres fronteiras.

**Primeira modelagem.** 14 tabelas, maquina de estados da vaga como enum, RLS em 7 tabelas,
controle de migracao com sha256 por arquivo.

**Banco isolado.** Container proprio no 55432, separado do PostgreSQL 18 nativo no 5432 que
atende a disciplina de banco de dados. ADR 0004.

**Oito ADRs** cobrindo Q1, Q2, Q3, Q4, Q8, Q21 e Q22 do plano, e um modelo de ameacas que
amarra cada uma das 15 ameacas ao ponto do codigo que a contem.

## O que a verificacao revelou

Nada aqui foi assumido: cada item abaixo apareceu ao rodar, nao ao ler.

### Confirmacoes

- **Baseline pt e en fecham GO em uma pagina.** O extrator aplicou exatamente as duas correcoes
  que o plano 15.1 previa: `\tech{face_recognition}` sem escape e `## \end{document}` com resto
  de markdown. Sem elas o en nao compila. Confirma a secao 15 do plano com execucao.
- **As invariantes do banco barram o que devem barrar**, testado contra Postgres real: versao
  com 2 paginas recusada por constraint; segunda candidatura na mesma vaga recusada; nota 150 e
  confianca 1.5 recusadas; evento de email nao autenticado com confianca 1.0 recusado pela RLS;
  `UPDATE` em auditoria negado ao papel de aplicacao.
- **O cluster da disciplina ficou intocado**: zero roles `pleito*` no 5432.
- **Rotacao de senha funciona**: a nova autentica, a antiga passa a ser recusada.

### Problemas encontrados e corrigidos

| # | Problema | Consequencia se passasse | Correcao |
| --- | --- | --- | --- |
| 1 | o guia copiado para `docs/` contem o telefone pessoal, e o repo e publico | telefone exposto na internet | guia fora do git, caminho em `PLEITO_GUIA`, `.tex` e `.pdf` no gitignore |
| 2 | `.env.example` trazia o email real em `PGADMIN_EMAIL` | email num arquivo publico | trocado por `preencha@exemplo.com` |
| 3 | `make migrar` rodado duas vezes falhava em `type "senioridade" already exists` | setup nao reproduzivel, quem clona trava | `scripts/migrar.sh` com tabela `migracao` e sha256 por arquivo |
| 4 | `migrar` nao passava `POSTGRES_APP_PASSWORD` para dentro do container | `pleito_app_login` ficava com **senha vazia** | variavel repassada no `exec` |
| 5 | `PLEITO_USER_AGENT` tem parenteses sem quote | `source .env` quebrava e o make abortava | valor entre quotes |
| 6 | `psql` nao interpola `:'senha'` em `-c` | rotacao silenciosamente sem efeito | `ALTER ROLE` por stdin, que tambem tira a senha do `ps` |
| 7 | `grep` e funcao do hook do rtk e resume a saida | `grep ... \| cut \| pbcopy` copiava vazio | `make senha-banco`, e `awk` na documentacao |

O item 4 e o mais grave dos sete: teria criado um papel de aplicacao sem senha num banco com
dado pessoal. O 1 e o 2 sao os de impacto externo, e os dois foram pegos na varredura antes do
primeiro push, nao depois.

## O que ainda nao sabemos

- existe volume real de vaga de estagio e junior nas fontes, ou o escopo precisa abrir
- Gupy e Solides permitem coleta automatizada pelos termos de uso (Q14 do plano)
- os campos que a triagem precisa chegam completos ou chegam sujos
- e possivel detectar a pagina de confirmacao de envio, que sustenta todo o ciclo da secao 18.4
- qual a taxa de vaga repetida entre fontes

## Proximo passo

Ingest das tres APIs publicas, que e leitura e nao tem efeito colateral externo:

```bash
.venv/bin/python -m viabilidade.cli ingest greenhouse lever ashby --limite 40
.venv/bin/python -m viabilidade.cli eda
```

Antes disso, revisar as empresas em `config/fontes.yaml`: a lista atual foi chutada para dar
forma ao codigo e nao reflete escolha do Filipe.

Depois: Gupy e Solides, que respondem a Q14. E so entao o egress, comecando em dry-run.

## Pendencias conhecidas

- `config/fontes.yaml` com empresas nao revisadas
- `git config user.name` e `list`, e assina os commits do repo publico
- ajustes no guia previstos no plano 15.1 alem dos dois erros do en, ainda nao aplicados
- constraints de worktree e paralelizacao, a definir depois do spike, ver `CLAUDE.md`
