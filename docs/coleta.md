# Coleta de vagas

Fontes, limites e como acrescentar uma. Tudo que muda por fonte fica em `config/fontes.yaml`;
o código só traduz a resposta em `VagaBruta`.

## Regras que valem para toda fonte (`src/coletor/base.py`)

- allowlist: só domínio de fonte com `ativa` verdadeiro; redirect para fora dela é recusado
  antes de requisitar o destino, e redirect para `http` ou para host que o `robots.txt` proíbe
  também
- termos: sem `termos.revisado_em` e veredito `permite` ou `permite_com_condicao` a fonte não
  coleta (`docs/fontes-termos.md`)
- rps: `PLEITO_RATE_LIMIT_RPS` do `.env`, aplicado a cada requisição, inclusive à repetição
  depois de 429
- 429: até `rede.tentativas` (`config/limites.yaml`) tentativas; entre elas espera
  `backoff_429.base_s` dobrando a cada vez, no máximo `backoff_429.max_s`; o `Retry-After` pode
  alongar a espera, nunca passar do teto. Acabadas as tentativas, a fonte devolve o 429 como erro

## Fontes de ATS por empresa (F4.6)

| Fonte | Endpoint (em `fontes.<slug>.endpoint`) | Identificador |
| --- | --- | --- |
| `workable` | `apply.workable.com/api/v1/widget/accounts/{identificador}` | conta |
| `smartrecruiters` | `api.smartrecruiters.com/v1/companies/{identificador}/postings` | empresa (diferencia maiúscula) |
| `personio` | `{identificador}.jobs.personio.de/xml` | subdomínio |

As três nascem com `ativa: false` e `termos.veredito: pendente`, sem `revisado_em`: os termos de
uso delas ainda não foram lidos. Para ligar uma, o Filipe lê a página em `termos.link`, preenche
`revisado_em` e `veredito`, troca `ativa` para `true` e registra a leitura em
`docs/fontes-termos.md`. Nenhum código muda.

`empresas_alvo` lista cada empresa com o `ats` que já se sabe (`ats: {workable: conta}`). Só o
que está em `ats` é coletado. `candidatos` opcional dá identificadores extras para a descoberta.

## Descoberta do identificador

`.venv/bin/python -m src.coletor.descoberta` tenta, para cada empresa sem board em um ATS ligado,
os candidatos tirados do nome (colado, com hífen, primeira palavra) e de `candidatos`, até
`ats.candidatos_max` por ATS. Passa pelas mesmas regras da coleta. Só vira sugestão quem responde
200 com ao menos uma vaga. A saída vai para `ats.saida_descoberta` (em `dados/`) como
`sugestoes` e `erros`; nunca altera `config/fontes.yaml`. Para ativar, o Filipe confere a empresa
e copia o identificador para `ats` em `empresas_alvo`.

## Relatório por rodada

`.venv/bin/python -m src.coletor.rodada` imprime uma linha por fonte de ATS: ligada ou
desligada, vagas, únicas, completude média (campos de triagem preenchidos) e erros. Marca
`corte_sugerido` quando a fonte fica abaixo de `ats.relatorio.vagas_minimas` ou
`completude_minima`. A rodada não grava no banco: a gravação pede a linha da fonte em `fonte`
(migration à parte).

## Acrescentar uma fonte

1. entrada em `config/fontes.yaml`: `dominios`, `endpoint`, `termos` pendentes, `ativa: false`
2. classe em `src/coletor/` com `@registrar`, `slug` e `_traduzir` (herde de `ColetorAts` para
   ATS por empresa)
3. teste offline com `respx`, incluindo sem termos, redirect fora da allowlist e 429
4. ler os termos, preencher `termos` e só então `ativa: true`

Gupy não tem coleta direta (ADR 0025); entra por alerta de email (F4.5).
