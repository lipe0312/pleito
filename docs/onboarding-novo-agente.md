# Prompt de onboarding — novo agente no projeto `pleito`

> Cole este arquivo inteiro como primeira mensagem para um novo agente (Claude Code ou outro)
> assumir o projeto. Ele substitui uma explicação verbal: tudo que importa está aqui ou nos
> arquivos citados. Atualizado em 2026-09-28, após a etapa 0.5 da fundação.

---

## Quem você é e o que já existe

Você está assumindo o projeto **pleito** (repositório público: `github.com/lipe0312/pleito`),
um sistema local-first que busca vagas de estágio/júnior, gera uma variante do currículo em
LaTeX sob medida para cada vaga, e tenta aplicar de forma assistida — com um humano (Filipe)
aprovando cada etapa crítica no painel.

**O spike de viabilidade já terminou e está fechado.** Você não está começando do zero: há
código funcionando, 3554 vagas reais já coletadas em `dados/viabilidade/vagas.jsonl`, banco
modelado e rodando, testes passando. Leia antes de escrever qualquer linha:

1. `README.md` — visão geral e como rodar
2. `docs/PLANO.md` — o plano original completo (1043 linhas), é o documento-mãe de tudo
3. `docs/estado.md` — **leia isso primeiro de tudo**. Registro cronológico de 3 rodadas do
   spike: o que foi feito, o que a verificação revelou, os erros encontrados e corrigidos, o
   que falta. É o arquivo mais denso de contexto real desta sessão.
4. `docs/viabilidade.md` — veredito consolidado por fonte e por plataforma
5. `docs/eda.md` e `docs/cenarios.md` — perfil das vagas coletadas e funil por cenário de filtro
6. `docs/ameacas.md` — modelo de ameaças, 15 itens, cada um ligado ao trecho de código que o
   contém
7. `docs/banco.md` — como o banco está configurado, isolado do PostgreSQL da disciplina do
   Filipe (não mexer nesse outro banco, nunca)
8. `docs/adr/0001` a `docs/adr/0011` — cada decisão de arquitetura com contexto, decisão e
   consequências. Leia todas antes de propor mudança estrutural; é provável que a pergunta já
   tenha sido decidida e justificada ali.
9. `docs/adr/0012` a `docs/adr/0019` — decisões posteriores ao spike, incluindo OpenAI,
   destinatário configurável, fundação, fallback seletivo e privacidade de cache
10. `CLAUDE.md` — constraints de código e de commit deste repositório especificamente

## As perguntas do plano (`docs/PLANO.md`, seção 16) já respondidas nesta sessão

O plano tem 27 questões em aberto (Q1–Q27). As que foram fechadas durante o spike, com a
resposta e onde está registrada:

- **Q1 (nome do projeto):** `pleito`. ADR 0001.
- **Q3 (stack do painel):** Python 3.11 + FastAPI + HTMX, sem build de frontend. ADR 0005.
- **Q4 (banco):** Postgres 16 em Docker, isolado do Postgres 18 nativo que atende a disciplina
  de banco de dados do Filipe (`MATA_60_2026_2`, role `aluno`, porta 5432). O pleito usa porta
  55432, cluster totalmente separado. ADR 0004, `docs/banco.md`.
- **Q8 (slots ou `.tex` inteiro):** slots. LLM nunca escreve o documento inteiro, só preenche
  espaços controlados no template Jinja2. ADR 0007.
- **Q14 (Gupy e Sólides, viável?):**
  - **Gupy**: ingest sim (API pública, GO com ressalva — termos não permitem uso pleno, ver
    abaixo). Egress **não**: Cloudflare Turnstile ativo no login + termos proíbem "agregar,
    copiar ou duplicar" vagas. Decisão: Gupy nunca é plataforma de aplicação automática, vira
    pendência manual sempre. ADR 0011, `docs/estado.md` rodada 3.
  - **Sólides**: não tem API. Por HTTP simples, NO-GO (conteúdo montado no cliente). Por
    navegador, o conteúdo renderiza (73441 vagas anunciadas), mas os cartões apontam para
    subdomínio por empresa sem API própria. Fica documentada como possível, não implementada.
- **Q2, Q21 e Q22 (provedor e modelos):** OpenAI por chave de API no `.env`; modelos e custos
  registrados em configuração e tiers bloqueados até avaliação. ADRs 0012 e 0017.

Questões **ainda em aberto**, não tocadas nesta sessão: Q5, Q6, Q9–Q11, Q12–Q13, Q15–Q20,
Q23–Q27.
Não presuma resposta para elas — pergunte ao Filipe quando forem relevantes.

## O que a verificação revelou (não repita esses erros)

Dezessete defeitos foram encontrados **rodando** código real contra sistemas reais, não por
leitura. Os mais importantes, porque são armadilhas fáceis de reintroduzir:

- **robots.txt com status 4xx não é proibição** (RFC 9309): 4xx = indisponível = libera. Só
  429 e 5xx exigem recusar. Isso já está implementado em `src/coletor/conformidade.py` — não
  "simplifique" essa lógica achando que está errada.
- **Filtro de domínio do navegador precisa liberar assets estáticos de terceiro** (script,
  stylesheet, font, image), senão qualquer página renderizada no cliente (React, Next.js) fica
  invisível para o Playwright. Ver `viabilidade/egress/navegador.py`, `TIPOS_ESTATICOS`.
- **Detecção de formulário não pode exigir a tag `<form>`** — sites modernos montam formulário
  em JS sem essa tag. Ver `_tem_formulario` em `viabilidade/egress/fluxo.py`.
- **Detecção de CAPTCHA não pode ser por substring no HTML** — a palavra "recaptcha" aparece em
  scripts de sites sem nenhum widget visível. Checar elemento visível, não texto.
- **Allowlist de domínio precisa aceitar subdomínio por sufixo com ponto** (`visagio.gupy.io`
  deve passar se `gupy.io` está na lista; `malicioso-gupy.io` não deve). Ver `host_permitido`
  em `src/coletor/conformidade.py`.
- **Palavra genérica em português ("dados") não pode classificar pela descrição inteira** — "seus
  dados pessoais" aparece em qualquer texto de LGPD e inflava falsos positivos. Termo genérico
  só vale no título. Ver `src/triagem/regra.py`, `TERMOS_GENERICOS`.
- **Remetente de email não pode ser checado por substring** — `jobs-noreply@linkedin.com.golpe.net`
  contém a string do remetente legítimo. Sempre separar caixa e domínio, comparar domínio por
  igualdade exata. Ver `viabilidade/ingest/email_alertas.py`, `remetente_confiavel`.
- **RSS de terceiro é dado não confiável**: usar `defusedxml`, nunca `xml.etree` puro (XXE,
  bomba de entidades).

O texto completo de todos os 17 itens, com a consequência de cada um se não tivesse sido
pego, está em `docs/estado.md`.

## Decisões de segurança e de escopo que são regras do projeto, não sugestões

- **O sistema nunca lê, digita ou guarda senha de plataforma de vaga**, em lugar nenhum. Login
  é sempre manual, feito pelo Filipe, uma vez, dentro do perfil Playwright dedicado
  (`segredos/perfil_navegador`, fora do git). Script para abrir esse perfil sem fechar sozinho:
  `scripts/login_manual.py`.
- **Nunca tentar contornar controle anti-bot ativo** (CAPTCHA, Turnstile) nem transplantar
  sessão autenticada de outro navegador para o perfil de automação. Isso foi cogitado
  explicitamente para a Gupy e recusado — ver ADR 0011. Se você se pegar pensando em stealth
  patches, `navigator.webdriver`, ou extração de cookie de navegador pessoal, pare: essa
  decisão já foi tomada, é não.
- **LinkedIn nunca é automatizado no site**, só entra como fonte via parser de email de alerta
  do Gmail (`viabilidade/ingest/email_alertas.py`), testado e funcionando.
- **`dados/` e `segredos/` nunca entram em commit**, nem com `git add -f`. `.env` real nunca é
  versionado, só `.env.example` com campos vazios.
- **Egress em dry-run é o padrão.** Sempre para antes de clicar em submeter, sempre grava
  captura de cada etapa. Submit real exige `PLEITO_EGRESS_MODO=submit_real` no `.env` **mais**
  token de 16+ caracteres — dupla trava deliberada, nunca acontece por acidente ou default.
- **`CLAUDE.md` deste repo proíbe assinar commit** (sem `Co-Authored-By`, sem `Generated with`).
  Isso é constraint do repositório, aplique-a.
- **Sem comentário e sem docstring no código** — nome de função/variável carrega o significado;
  explicação vai para `docs/` ou ADR. Ver `CLAUDE.md`.
- **Banco do pleito é isolado do banco da disciplina do Filipe.** PostgreSQL 18 nativo em
  127.0.0.1:5432 com o banco `MATA_60_2026_2` e a role `aluno` **não é o banco do projeto** —
  não toque nele. O banco do pleito é o container Docker em 127.0.0.1:55432.

## Veredito atual do spike, por fronteira

| Fronteira | Status | Evidência |
| --- | --- | --- |
| Ingest | GO, 14 fontes, 10 viáveis | `docs/viabilidade.md`, `dados/viabilidade/ingest.json` |
| Baseline do currículo | GO, pt e en, 1 página | `dados/viabilidade/baseline.json` |
| Egress Greenhouse | GO com ressalva (dry-run) | `dados/viabilidade/egress/greenhouse.json` |
| Egress Ashby | GO com ressalva (dry-run) | `dados/viabilidade/egress/ashby.json` |
| Egress Gupy | NO-GO permanente, sempre pendência manual | ADR 0011 |
| Global | GO com ressalva | `docs/viabilidade.md` |

**O único item que falta para o egress virar GO pleno** (Greenhouse/Ashby): uma execução de
submit real autorizada pelo Filipe, numa vaga escolhida por ele, para provar que a página de
confirmação é detectável. Isso é uma decisão/ação do Filipe, não uma investigação técnica
pendente — não tente fazer isso sozinho sem ele escolher a vaga e autorizar explicitamente.

## O escopo de busca que o Filipe escolheu nesta sessão

Foco em **dados**, aceitando híbrido ou presencial em Salvador, sem exigir senioridade
declarada (muita vaga boa vem sem esse campo preenchido), filtrando por até 2 anos de
experiência exigidos. Configurado em `config/filtros.yaml`, cenário `"ESCOLHIDO dados hibrido
presencial-SSA sem senioridade ate 2 anos"`. Resultado na última coleta: 9 vagas de 3554,
nenhuma presencial em Salvador especificamente (achado ainda não investigado — pode ser
característica real do mercado ou termo de busca insuficiente na Gupy para essa cidade).

Isso é baixo para fluxo diário (`config/limites.yaml` prevê até 40 avaliadas/dia), mas o
gargalo é o cruzamento de critérios, não falta de vaga: a Gupy sozinha tem 1737 resultados para
"estágio" sem filtro de função. Rodar o ingest com regularidade tende a acumular volume.

## Comandos que você vai usar

```bash
cd ~/Documents/PESSOAL/DOCUMENTOS/Curriculos/pleito

# ambiente Python 3.11
cp .env.example .env   # se ainda não existe; gerar senhas com secrets.token_urlsafe(32)
make setup
make banco && make banco-status && make migrar

# spike / dados já coletados
.venv/bin/python -m viabilidade.cli ingest --limite 900    # roda as 14 fontes
.venv/bin/python -m viabilidade.cli eda                     # perfil das vagas
.venv/bin/python -m viabilidade.cli cenarios                 # funil por cenário
.venv/bin/python -m viabilidade.cli baseline --escrever      # extrai/valida currículo base
.venv/bin/python -m viabilidade.cli egress <url> --pdf <pdf> --plataforma <nome>
.venv/bin/python -m viabilidade.cli veredito                 # consolida tudo em docs/

# qualidade
make testes           # 73+ testes, todos offline
make lint

# login manual (única forma de autenticar sessão de egress)
.venv/bin/python scripts/login_manual.py <url>
```

## Estrutura do repositório

```
pleito/
  README.md                    visão geral, comandos, invariantes de segurança
  CLAUDE.md                    constraints deste repo (sem comentário, sem assinar commit...)
  docker-compose.yml           postgres + pgadmin (pgadmin fica off por profile)
  Makefile                     todos os comandos acima
  pyproject.toml                dependências e config do ruff/pytest
  .env.example                  template de variáveis, sem segredo real

  docs/
    PLANO.md                    o plano original (fonte de verdade do que construir)
    guia-adaptacao.md           NÃO EXISTE NO GIT — vive fora, caminho em PLEITO_GUIA no .env,
                                 porque contém o telefone pessoal do Filipe
    estado.md                   registro cronológico do spike, leia primeiro
    viabilidade.md               veredito consolidado, gerado por comando
    eda.md, cenarios.md          análise das vagas coletadas, gerados por comando
    ameacas.md                   modelo de ameaças
    banco.md                     como configurar/acessar o banco
    onboarding-novo-agente.md    este arquivo
    adr/0001 a 0019              decisões de arquitetura

  config/
    fontes.yaml                  as 14 fontes, domínios permitidos, boards por empresa
    filtros.yaml                 termos de busca, cenários de filtro, o escopo escolhido
    limites.yaml                  horários, limites diários, orçamento de LLM
    modelos.yaml                  tiering de modelo por etapa
    triagem.yaml                  vocabulário e limites da triagem

  db/
    migrations/0000_controle.sql  tabela de controle de migração (idempotência)
    migrations/0001_inicial.sql   schema completo: 14 tabelas, enums, estados da vaga
    policies/0001_papeis_rls.sql  RLS em 7 tabelas, papéis pleito_app/painel/leitura
    policies/0002_usuario_app.sql cria o usuário de login com senha do .env

  viabilidade/                   módulo do spike — todo o código testado nesta sessão
    contratos.py                  VagaBruta, enums (Senioridade, ModeloTrabalho, Funcao...)
    conformidade.py                robots.txt (RFC 9309), allowlist de domínio, rate limit
    config.py                      leitura de .env e config/*.yaml
    triagem.py                     classificador de função e extrator de anos de experiência
    cli.py                         comando `viabilidade` (ingest/eda/cenarios/baseline/egress/veredito)
    veredito.py                    consolida GO/NO-GO das 3 fronteiras
    ingest/                        um coletor por fonte (14 arquivos), + email_alertas.py, rss.py
    egress/                        navegador.py (Playwright), fluxo.py (o dry-run completo)
    baseline/                      extrair.py (do guia) e validar.py (compila e mede)
    eda/                           relatorio.py (perfil e cenários)

  src/                            implementação definitiva e compartilhada
    config.py                     carregamento comum de ambiente e YAML
    coletor/                      contratos e conformidade migrados do spike
    triagem/                      classificação e extração de experiência
    llm/ db/ painel/              roteador, orçamento, persistência e painel local

  scripts/
    migrar.sh                     aplica migrações com controle de idempotência
    rotacionar-senha.sh           gera senha nova, aplica ALTER ROLE, atualiza .env
    login_manual.py               abre perfil Playwright para login manual sem fechar sozinho

  tests/                         testes offline e testes de integração restritos ao banco do projeto
  dados/                          FORA DO GIT — vagas.jsonl, resultados de ingest/egress/baseline
  segredos/                       FORA DO GIT — perfil do navegador
```

## O que fazer a seguir (ordem sugerida, não obrigatória)

1. Se o Filipe autorizar: escolher com ele uma vaga do Greenhouse ou Ashby e rodar o submit
   real (`PLEITO_EGRESS_MODO=submit_real` + token no `.env`), fechando o único item pendente
   do veredito de egress.
2. Iniciar a Fase 1: integração segura do Gmail, resumo diário e telas Hoje/Candidaturas, conforme
   `docs/plano-direcionado.md`.
3. Investigar por que "presencial Salvador + dados" deu zero nesta coleta — pode precisar de
   termo de busca dedicado no `config/filtros.yaml` para a Gupy.
4. Perguntas em aberto do plano que bloqueiam decisão de arquitetura (Q9-Q13 etc.) — levar
   ao Filipe conforme forem ficando relevantes, não assumir resposta.

## Como se comportar neste projeto

- Teste contra sistema real antes de reportar viabilidade — leitura de documentação não é
  verificação, como os 17 achados desta sessão provam.
- Toda mudança de regra de segurança ou de veredito precisa de teste que falha sem ela.
- `rtk` para operação de git/build/inspeção de arquivo — exceto quando a saída alimenta outro
  comando num pipeline, aí use o binário direto (ele resume e quebra pipe).
- Nunca amplie o escopo de aplicação (nunca resolva CAPTCHA, nunca crie conta, nunca automatize
  LinkedIn) sem decisão explícita do Filipe — essas são linhas já traçadas, não pontos de
  julgamento seu.
