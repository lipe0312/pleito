# pleito

Sistema local-first que busca vagas de estagio e junior, gera uma variante do curriculo em LaTeX
para cada vaga boa, aplica de forma assistida e acompanha o retorno pelo Gmail.

Estado atual: **fase de spike de viabilidade**. Nenhuma fase do roteiro comeca antes de o
veredito global fechar GO. A flag `sistema_ativo` nasce desligada no banco.

## Por que esse spike vem antes de tudo

O sistema tem duas fronteiras externas que nao estao sob controle da maquina do Filipe:

- **ingest**: conseguir trazer vagas das fontes, respeitando robots.txt e termos de uso
- **egress**: conseguir enviar uma candidatura de verdade e capturar a prova de envio

Todo o resto (banco, painel, blocos, familias, campeoes, tiering de modelos) e codigo
deterministico local: se falhar, e bug, e se corrige. As duas fronteiras acima podem ser
**bloqueio duro** (termos que proibem, CAPTCHA, muro de login, ausencia de API). O modulo
`viabilidade/` existe para separar *"da trabalho"* de *"nao da"*, com teste que roda e prova.

Ver `docs/viabilidade.md` para o veredito corrente e `docs/adr/0007` para a decisao.

## Estrutura

```
viabilidade/        modulo do spike, descartavel sem tocar em src/
  ingest/           um coletor por fonte, todos atras de robots.txt e allowlist de dominio
  egress/           Playwright com perfil persistente, dry-run que para antes do submit
  baseline/         extrai os dois curriculos base do guia, corrige e valida a compilacao
  eda/              perfil das vagas coletadas, completude, duplicidade, elegibilidade
  veredito.py       consolida GO / GO com ressalva / NO-GO por fronteira
config/             filtros, fontes, limites, modelos (nada hardcoded no codigo)
db/migrations/      primeira modelagem
db/policies/        papeis e RLS
src/                modulos do sistema definitivo, ainda vazios
docs/adr/           decisoes de arquitetura em formato MADR minimo
```

## Setup

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'   # gere cada senha
make setup
make banco
make migrar
make testes
```

## Comandos do spike

```bash
.venv/bin/python -m viabilidade.cli baseline --escrever
.venv/bin/python -m viabilidade.cli ingest greenhouse lever ashby --limite 40
.venv/bin/python -m viabilidade.cli ingest gupy solides
.venv/bin/python -m viabilidade.cli eda
.venv/bin/python -m viabilidade.cli egress "<url da vaga>" --pdf templates/../dados/viabilidade/baseline/cv_pt.pdf
.venv/bin/python -m viabilidade.cli veredito
```

`ingest` e `eda` nao tem efeito colateral externo. `egress` roda em `dry_run` por padrao: abre,
preenche, anexa, encontra o botao e **para antes de clicar**, gravando captura de cada etapa.
Submit real exige `PLEITO_EGRESS_MODO=submit_real` mais um token de 16+ caracteres no `.env`,
e e uma decisao por execucao (ver `docs/adr/0008`).

## Invariantes de seguranca

- nenhuma senha e guardada, digitada ou lida pelo sistema, em lugar nenhum
- coleta so em dominio listado em `config/fontes.yaml`, sempre depois de consultar robots.txt
- LinkedIn nunca e automatizado, entra so por email de alerta
- CAPTCHA nunca e resolvido, vira NO-GO ou pendencia
- o navegador do egress bloqueia toda requisicao para dominio fora da allowlist
- `dados/` e `segredos/` nunca entram no git
- curriculo com mais de uma pagina e recusado por constraint no banco, nao so por codigo

## Dado pessoal e repositorio publico

O guia de adaptacao contem o curriculo base completo, com telefone. Ele **nao e versionado**:
mora fora do repositorio e o caminho vem de `PLEITO_GUIA` no `.env`, com default
`../base/guia-adaptacao-curriculo-filipe-santana.md`. O mesmo vale para os `.tex` e `.pdf`
extraidos dele, que sao gerados por comando e ficam no `.gitignore`.

Quem clonar este repositorio consegue rodar os testes, o lint e o banco, mas nao obtem o
curriculo nem nenhum dado de contato.
