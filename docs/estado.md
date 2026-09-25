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
