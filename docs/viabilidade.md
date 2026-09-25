# Veredito de viabilidade

Gerado por `python -m viabilidade.cli veredito`. Este arquivo e sobrescrito pelo comando.

**Veredito global: nao testado**

## Ingest por fonte

| fonte | veredito | como testar |
| --- | --- | --- |
| greenhouse | nao testado | `cli ingest greenhouse`, API publica de job board por empresa |
| lever | nao testado | `cli ingest lever`, API publica de postings por empresa |
| ashby | nao testado | `cli ingest ashby`, API publica de job board |
| gupy | nao testado | `cli ingest gupy`, Q14 do plano, depende de robots e leitura dos termos |
| solides | nao testado | `cli ingest solides`, sem API publica conhecida |
| linkedin_alertas | nao testado | depende da fase 1, entrada por email, site nunca automatizado |

## Egress por plataforma

| plataforma | veredito | como testar |
| --- | --- | --- |
| gupy | nao testado | `cli egress <url> --pdf <pdf>` em dry_run, depois uma execucao real autorizada |

## Baseline do curriculo

| idioma | veredito | observacao |
| --- | --- | --- |
| pt | go | compila limpo, 1 pagina, sem overfull |
| en | go | 1 pagina apos as duas correcoes previstas no plano 15.1 |

## Criterio de GO

Ingest por fonte: GO exige robots permitindo, ao menos 5 vagas e 70% de completude media nos
campos que a triagem usa. Termos de uso nao lidos limitam a fonte a GO com ressalva.

Egress: dry-run bem sucedido vale no maximo GO com ressalva. GO pleno exige uma execucao real
autorizada com prova de confirmacao detectada.

Global: o pior veredito entre as tres fronteiras. Sem egress testado, o global fica em
nao testado, e a flag `sistema_ativo` permanece desligada.
