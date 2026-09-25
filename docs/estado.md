# Onde estamos

Atualizado em 2026-09-25. Registro corrente do projeto. `docs/viabilidade.md` guarda o veredito
por fronteira, `docs/eda.md` o perfil das vagas e `docs/cenarios.md` o funil por cenario, todos
gerados por comando.

## Resumo

**Veredito global: GO com ressalva.** O projeto e viavel. As tres fronteiras foram testadas com
dado real, nao com leitura de documentacao.

- **ingest: 10 de 11 fontes viaveis**, 2484 vagas coletadas numa rodada, 0,6% de duplicidade
- **egress: 2 de 3 plataformas viaveis** em dry-run, com PDF anexado e campos mapeados
- **baseline: GO** em pt e en, uma pagina, sem estouro de caixa

A ressalva do global tem duas causas, ambas conhecidas e nenhuma bloqueante:
1. dry-run nunca vale GO pleno por construcao, so uma execucao real autorizada fecha a prova
2. a Gupy exige sessao autenticada para aplicar, resolvel com login manual uma vez no perfil
   persistente, que e exatamente o que o plano 10.7 prescreve

## Ingest: o que temos

| fonte | tipo | veredito | vagas | completude |
| --- | --- | --- | --- | --- |
| gupy | portal BR | GO com ressalva | 600 | 95% |
| greenhouse | ATS por empresa | GO | 600 | 74% |
| ashby | ATS por empresa | GO | 600 | 81% |
| arbeitnow | agregador | GO | 250 | 76% |
| hackernews | thread Who is hiring | GO | 211 | 91% |
| remoteok | agregador | GO | 99 | 90% |
| jobicy | agregador | GO | 50 | 90% |
| lever | ATS por empresa | GO | 35 | 84% |
| himalayas | agregador | GO | 20 | 94% |
| remotive | agregador | GO | 19 | 96% |
| solides | portal BR | NO-GO | 0 | - |

A ressalva da Gupy e a leitura dos termos de uso, nao capacidade tecnica: robots.txt libera,
a API do portal de empregabilidade e publica e sem chave, e sozinha oferece 1737 vagas para
"estagio" e 1038 para "junior". E a unica fonte que entrega volume brasileiro.

Solides e o unico NO-GO: a listagem responde 200 mas monta o conteudo no cliente, sem link de
vaga no HTML inicial nem JSON embutido. So seria viavel por navegador headless, o que muda
custo e perfil de risco. Dado que a Gupy cobre o mercado brasileiro, nao compensa.

LinkedIn segue pelo caminho do plano: parser de email de alerta, testado offline, sem nunca
automatizar o site.

## O funil, com dado real

Sobre 2484 vagas coletadas:

| etapa | vagas | % |
| --- | --- | --- |
| coletadas | 2484 | 100% |
| de tecnologia (engenharia, dados, infra, qa) | 1090 | 43,9% |
| estagio ou junior, qualquer funcao | 690 | 27,8% |
| **funil final: estagio ou junior, tech, ate 2 anos exigidos** | **303** | **12,2%** |
| funil final no Brasil | 269 | 10,8% |
| funil final remoto | 19 | 0,8% |

303 vagas por rodada de coleta e mais do que o plano precisa: `config/limites.yaml` prevê 40
vagas avaliadas por dia. O gargalo nao vai ser falta de vaga.

## Egress: o que conseguimos enviar

| plataforma | veredito | formulario | PDF anexado | campos | obrigatorios | bloqueio |
| --- | --- | --- | --- | --- | --- | --- |
| greenhouse | GO com ressalva | sim | sim | 75 | 54 | - |
| ashby | GO com ressalva | sim | sim | 64 | 5 | - |
| gupy | NO-GO | atras do login | nao | - | - | exige sessao autenticada |

No Greenhouse os campos obrigatorios vieram rotulados em portugues: Nome, Sobrenome, E-mail,
Pais, Telefone, Localizacao, Escola, Escolaridade. Todos cobertos pelo banco de respostas da
secao 9 do plano.

No Ashby apareceu uma pergunta aberta obrigatoria ("Please provide an example or evidence of
your exceptional ability") e um campo de disponibilidade. Sao exatamente o caso `pergunta_nova`
que o plano manda virar pendencia com rascunho, em vez de resposta automatica.

Nenhuma candidatura foi enviada. O dry-run para antes do clique e grava captura de cada etapa.

## O que a verificacao revelou nesta fase

Onze problemas encontrados rodando, todos corrigidos. Os cinco primeiros teriam produzido
veredito errado, ou seja, teriam feito o projeto parecer inviavel sem ser.

| # | Problema | Consequencia se passasse | Correcao |
| --- | --- | --- | --- |
| 1 | robots.txt com status 4xx era tratado como proibicao | Ashby e Jobicy reprovadas sem proibicao real; contraria a RFC 9309 | 4xx libera, 429 e 5xx recusam, com teste parametrizado |
| 2 | filtro de dominio do navegador abortava os assets do proprio site | Ashby parecia nao ter formulario; qualquer pagina renderizada no cliente ficaria invisivel | asset estatico de terceiro passa, navegacao e xhr seguem restritos |
| 3 | `achar_formulario` exigia tag `<form>` | Ashby monta 64 campos em React sem `<form>`: plataforma viavel dada como NO-GO | formulario e `<form>` ou 3+ campos na pagina |
| 4 | deteccao de CAPTCHA por substring no HTML | Greenhouse reprovado por falso positivo: a palavra recaptcha aparece 8 vezes em script, sem nenhum widget | conta widget visivel; script invisivel vira evidencia, nao bloqueio |
| 5 | fluxo nao esperava renderizacao nem seguia o link de aplicar | pagina de descricao lida como ausencia de formulario | networkidle mais espera de assentamento, e passo que segue o link de aplicar |
| 6 | URL de URL da Gupy nao casava a allowlist | subdominio `visagio.gupy.io` bloqueado com `gupy.io` liberado; checagem do navegador e do http divergiam | match por sufixo com ponto, compartilhado pelas duas, e teste que recusa `malicioso-gupy.io` |
| 7 | endpoint da Gupy errado | 404 em tudo; a fonte mais importante do Brasil dada como sem dados | `employability-portal.gupy.io/api/v1/jobs` |
| 8 | parametro de busca da Gupy era `name` | 404 silencioso | `jobName` |
| 9 | termos de busca com duas palavras na Gupy | a API casa frase: "estagio backend" devolve 0 e "estagio" devolve 1737 | termos por fonte em `filtros.yaml` mais paginacao |
| 10 | URLs do HN vinham com barra como entidade HTML | 257 comentarios lidos e zero vagas extraidas | unescape antes de extrair URL |
| 11 | senioridade indefinida em 64% das vagas | parecia falha do classificador de senioridade | a EDA mostrou que sao vagas de outra area: faltava filtro de **funcao**, nao de senioridade |

O item 11 e o mais valioso: a amostra de indefinidas era Product Manager, Course Writer,
Executivo Comercial, Auxiliar de Logistica, Office Assistant. O plano filtra por senioridade
(secao 6.1) mas o ruido dominante e area errada. Foi acrescentado `viabilidade/triagem.py` com
classificador de funcao e extrator de anos de experiencia exigidos, ambos deterministicos.

## O que ainda nao sabemos

- se a pagina de confirmacao de envio e detectavel, que sustenta o ciclo da secao 18.4. So uma
  execucao real autorizada responde
- se o email de confirmacao chega e e associavel a vaga, que depende da fase 1
- se os termos de uso da Gupy permitem uso automatizado. Robots libera, os termos nao foram lidos
- se o login manual no perfil persistente sustenta sessao por quanto tempo na Gupy

## Proximo passo

1. Ler os termos de uso da Gupy e decidir a Q14 com base no texto, nao em robots
2. Login manual uma unica vez no perfil persistente, e repetir o dry-run da Gupy para ver se o
   formulario de candidatura aparece autenticado
3. Uma execucao de submit real autorizada, numa vaga escolhida pelo Filipe, para fechar a prova
   de confirmacao e levar o egress a GO pleno
4. Revisar `config/fontes.yaml`: as empresas foram sondadas por mim, nao escolhidas

## Pendencias conhecidas

- `git config user.name` e `list`, e assina os commits do repo publico
- ajustes no guia previstos no plano 15.1 alem dos dois erros do en
- Workable e SmartRecruiters tem endpoint valido e identificador desconhecido, registrados em
  `config/fontes.yaml` sob `descobertas_pendentes`
- constraints de worktree e paralelizacao, a definir, ver `CLAUDE.md`

---

# Rodada 2 (2026-09-25): foco em remoto, dados, estagio e junior

## LinkedIn: sim, pelo caminho do email

Verificado na caixa real: chegam alertas de `jobs-noreply@linkedin.com`, com assuntos como
"Novas vagas semelhantes a de Software Development Intern na iHerb" e "Programa de Estagio
Santander 2026". O corpo em texto plano tem estrutura fixa e limpa:

```
Titulo da vaga
Empresa
Cidade
Visualizar vaga: https://www.linkedin.com/comm/jobs/view/<id>?<rastreio>
```

O parser foi reescrito orientado a linha e testado contra esse formato. Extrai titulo, empresa
e local alinhados, ignora o link de cabecalho e os de busca, e **descarta o rastreio**: a URL
guardada e `https://www.linkedin.com/jobs/view/<id>`, sem query.

Um teste de remetente forjado encontrou um furo real: `jobs-noreply@linkedin.com.golpe.net`
passava na checagem por substring. Qualquer um pode registrar esse dominio e injetar vagas
falsas. A checagem agora separa caixa e dominio e compara o dominio exato.

**Fetch autenticado do site do LinkedIn nao foi implementado e nao e recomendado.** E o unico
caminho que a secao 10.7 do plano proibe, viola os termos de uso e arrisca a conta. O email de
alerta entrega o mesmo algoritmo personalizado da conta, com risco zero.

## Solides: nao, nao foi descartada

O NO-GO anterior valia so para coleta por HTTP. Pelo navegador a pagina **renderiza**: o site
anuncia 73441 oportunidades e a primeira ja aparece com titulo, empresa, cidade e salario.

O que o teste revelou: os cartoes nao linkam para `/vaga/...`, linkam para **subdominio por
empresa**, como `drogal.vagas.solides.com.br`. A Solides e um diretorio de paginas de carreira,
o mesmo padrao da Gupy. Os subdominios nao expoem API: `/api/v1/jobs`, `/api/jobs` e
`/api/vagas` devolvem 404, e `/_next/data` devolve 403.

Conclusao: viavel apenas por navegador, com custo por pagina. Fica como opcao documentada, nao
implementada, porque a Gupy ja entrega o volume brasileiro por API.

## Fontes novas nesta rodada

Cinco fontes e 34 boards novos. Total agora: 14 fontes, 3554 vagas por rodada.

| fonte | tipo | vagas |
| --- | --- | --- |
| weworkremotely | RSS remoto | 84 |
| workingnomads | API remoto | 57 |
| jobspresso | RSS remoto | 10 |
| greenhouse | +15 boards de dados e remote-first | 900 |
| ashby | +14 boards de dados e remote-first | 900 |
| lever | +1 board | 54 |

Os boards novos sao de empresas de dados e remote-first: Databricks, Snowflake, MongoDB,
Cloudflare, Fivetran, ClickHouse, Grafana, Airbyte, Astronomer, Confluent, dbt, Hightouch,
Sigma, Neo4j, Starburst, CockroachDB, Sentry, Zapier, PostHog, Atlan, Prefect, Materialize,
Metabase, Hex, Monte Carlo, Percona, Buffer, Vercel, Remote.com e outros.

A Gupy ganhou os filtros nativos que a API aceita: `workplaceType=remote` e
`type=vacancy_type_internship`, com recortes configuraveis em `filtros.yaml`. Sozinha ela tem
2088 vagas remotas e 47 estagios remotos.

RSS e texto de terceiro nao confiavel, entao o parser usa `defusedxml`, com teste que recusa
entidade externa e bomba de entidades.

## O numero que voce precisa ver

Escopo estrito: **remoto + dados + estagio ou junior = 3 vagas em 3554**, de 2 fontes.

| recorte | vagas | fontes |
| --- | --- | --- |
| dados + estagio/junior + remoto | 3 | 2 |
| dados + estagio/junior + remoto ou hibrido | 8 | 2 |
| dados + estagio/junior + qualquer modelo | 21 | 4 |
| dados + estagio/junior/sem senioridade + remoto, ate 2 anos | 26 | 8 |
| **dados + estagio/junior/sem senioridade + remoto ou hibrido, ate 2 anos** | **35** | **8** |
| tech + estagio/junior + remoto | 25 | 9 |
| tech + estagio/junior + qualquer modelo | 141 | 11 |

Das 21 vagas de dados para estagio ou junior, apenas 3 sao remotas: 8 sao presenciais e 5
hibridas. **Estagio em dados no Brasil e majoritariamente presencial.** Isso e mercado, nao
limitacao de ferramenta: 14 fontes e 3554 vagas produzem esse numero.

O recorte com melhor relacao entre volume e aderencia e o da linha destacada: aceitar hibrido e
aceitar vaga sem senioridade declarada, filtrando por ate 2 anos de experiencia exigidos. Sai
de 3 para 35 vagas sem sair da area de dados.

Ampliar para engenharia leva a 141 vagas em qualquer modelo, mas a amostra mostra que incluir
senioridade indeclarada em tech traz ruido: cargos como Security Engineer e Inference Engineer
da OpenAI entram sem serem junior.

## Defeitos corrigidos nesta rodada

| # | Problema | Correcao |
| --- | --- | --- |
| 12 | remetente do LinkedIn checado por substring: `jobs-noreply@linkedin.com.golpe.net` era aceito | caixa e dominio separados, dominio comparado por igualdade |
| 13 | parser do alerta desalinhava os campos, porque a linha do link comeca com "Visualizar vaga:" | parser orientado a linha, com rotulo reconhecido |
| 14 | a palavra "dados" aparece em qualquer descricao em portugues ("seus dados pessoais"), e classificava vaga administrativa como dados | termos genericos so valem no titulo, nunca na descricao. 145 caiu para 121 vagas de dados, 24 falsos positivos removidos |
| 15 | siglas comuns em portugues nao eram reconhecidas: "Analista de BI Junior" ficava indefinida | siglas com fronteira de palavra: bi, etl, ml, nlp, dw, sre, qa, sdet |
| 16 | RSS de terceiro parseado com `xml.etree`, vulneravel a XXE e bomba de entidades | `defusedxml` com teste dos dois ataques |
| 17 | `vagas.solides.com.br` dado como sem dados por seletor errado no navegador | o conteudo renderiza; os cartoes apontam para subdominio por empresa |

## Decisao pendente sua

O escopo remoto mais dados mais estagio nao sustenta um fluxo diario: sao 3 vagas. Escolha uma
direcao antes da proxima fase:

1. aceitar hibrido e vaga sem senioridade declarada, filtrando por ate 2 anos: 35 vagas, segue
   so em dados
2. incluir engenharia junto de dados: 25 remotas ou 141 em qualquer modelo, com mais ruido
3. aceitar presencial em Salvador e regiao: recupera as 8 presenciais de dados
4. manter o escopo estrito e aceitar fluxo de poucas vagas por semana
