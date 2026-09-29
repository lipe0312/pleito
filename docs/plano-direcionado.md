# Plano direcionado do pleito

Escrito em 2026-09-28, depois do spike, das decisões das ADRs 0011 a 0017 e da revisão da Fase 0.
Não substitui o `docs/PLANO.md`: é o caminho até o produto final, já com as decisões aplicadas.
Cada fase diz o objetivo, o que o Filipe passa a ver, o que criar e quando está pronta.
Quem implementar analisa a viabilidade de cada ponto e propõe ajuste antes de discordar em código.

## Andamento

Legenda: [x] concluído e verificado, [ ] pendente.

- [x] Spike de viabilidade, veredito GO com ressalva (`docs/viabilidade.md`)
- [x] Fase 0, fundação: banco com papéis e RLS, auditoria, flag, roteador LLM com orçamento,
  painel vazio (commits 4588e24, de48423, 3af8c71, e7eaa7f)
- [x] Etapa 0.5, ajustes da revisão (commits bbbfb7b, b75f05b, a4d6496, 4efa4f6)
- [x] Rótulos `Candidaturas/*` criados na conta do Gmail
- [x] ADRs 0001 a 0019 versionadas
- [x] Pré-requisitos da Fase 1 no Google Cloud e no `.env` (seção abaixo); falta só a autorização
  interativa e o push no iPhone
- [ ] Fase 1 a Fase 9 e monitor de disponibilidade

## Contexto a ler antes de implementar

Ordem de leitura. Quem começa uma fase relê o que ela toca; nada aqui é opcional.

**Regras e estado**
- [x] `CLAUDE.md`: constraints de código, commit e fluxo
- [x] `docs/onboarding-novo-agente.md` e `docs/estado.md`: o que o spike provou e os 17 defeitos achados
- [x] `docs/plano-direcionado.md`: este arquivo

**Plano-mãe**, `docs/PLANO.md`, por fase:
- todas: seção 3 (arquitetura e roteador), 10 (segurança), 12 (custo), 13 (dados), 14 (roteiro),
  16 e 18.7 (questões em aberto)
- Fase 1: 4.8 (acompanhamento por email), 8.5 (validação de eventos de email), 10.6 (Gmail),
  18.6 (organização do Gmail)
- Fase 2 e 3: 7 (currículo, blocos, famílias, uma página), 8.1 a 8.4, 8.6 (conjunto de avaliação)
- Fase 4: 4.1 a 4.3, 6 (filtros e pontuação), 11 (fontes)
- Fase 5: 5 (painel), 7.6 a 7.8 (uma página, retenção, chat)
- Fase 6: 4.6, 4.7, 9 (banco de respostas), 10.7 (navegador), 18.3 e 18.4 (diversidade e confirmação)
- Fase 7: 7.9 e 18.5 (campeões)

**Decisões**, `docs/adr/`:
- [x] 0001 a 0011: nome, spike, dry-run, banco, painel, LLM por tier, slots, segredos, função antes
  de senioridade, fontes, Gupy manual
- [x] 0012 a 0014: OpenAI por API e orçamento, resumo por email, celular descartado
- [x] 0015 a 0019: triagem em config, permissões do banco, registro e orçamento do roteador,
  fallback de saldo, cache de prompt desligado

**Configuração**, `config/`:
- [x] `limites.yaml` (horários, orçamento, limites), `modelos.yaml` (tiers, preços, habilitação),
  `triagem.yaml`, `filtros.yaml`, `fontes.yaml`, `painel.yaml`
- [ ] a criar: `emails.yaml`, `rotulos.yaml` (Fase 1)

**Código e banco**
- [x] `src/config.py`, `src/llm/roteador.py`, `src/llm/orcamento.py`, `src/db/`, `src/painel/`
- [x] `db/migrations/0000` a `0002`, `db/policies/0001` a `0003`, `docs/banco.md`
- [x] `viabilidade/ingest/email_alertas.py`: origem do verificador de remetente da Fase 1
- [x] `tests/`: 146 testes offline e 11 de banco

## Objetivo em alto nível

Antes das 8h de cada dia, o Mac busca vagas de estágio e júnior em dados, descarta as ruins sem
gastar token, avalia só as promissoras, prepara um currículo sob medida para as melhores e manda
um email de resumo que notifica o iPhone. O Filipe abre o painel local, revisa o que mudou no
currículo e aprova. A aplicação é assistida, para no último clique por padrão, e o envio real é
sempre decisão dele. As respostas das empresas chegam por email, são organizadas em pastas por
etapa e atualizam o status sozinhas. O gasto com IA é pequeno, mensal e nunca é feito à toa.

## Decisões já tomadas

| Tema | Decisão | Onde |
| --- | --- | --- |
| Servidor | Só o Mac. Celular descartado; Mac dormindo é resolvido com despertar agendado (`pmset`) | ADR 0014 |
| IA | OpenAI por chave de API no `.env`, dois tiers: `gpt-6-luna` (rápido) e `gpt-6-sol` (forte) | ADR 0012, 0017 |
| Gasto | Orçamento mensal (US$ 5,00) com teto diário e reserva antes de cada chamada | ADR 0012, 0017 |
| Sem gasto à toa | Duplicata, filtros e pré-nota antes do modelo forte; dia sem vaga boa não chama nada | ADR 0012 |
| Ativação da IA | Tiers desabilitados até passar no conjunto de avaliação (seção 8.6 do plano) | ADR 0017 |
| Aviso diário | Email de resumo antes das 8h com o rótulo `Candidaturas/Prontas`; destino em `.env` | ADR 0013 |
| Pastas do Gmail | `Candidaturas/` com Prontas, Aplicadas, Em andamento, Teste, Entrevista, Oferta, Encerradas, Classificar, Suspeitos. Já criadas na conta | ADR 0013 |
| Gupy | Nunca automatizada: vira pendência manual com o material pronto | ADR 0011 |
| LinkedIn | Nunca automatizado; só entra como fonte por email de alerta | plano 10.7 |
| Banco | Postgres 16 em Docker, isolado do banco da disciplina, permissões por papel e coluna | ADR 0004, 0016 |
| Painel | FastAPI + HTMX, só em loopback, sem CDN | ADR 0005 |

## Decisão de orçamento resolvida

Com o saldo abaixo de US$ 2,00, somente `pontuacao_final` pode usar o modelo rápido; a
classificação de email já é rápida. Escrita de currículo e chat ficam adiados. Esgotamento do
teto diário ou mensal bloqueia a chamada sem fallback. ADR 0018 registra a exceção controlada.

## Etapa 0.5: ajustes da Fase 0 concluídos

Etapa concluída; decisões e verificações:

1. Fallback seletivo de pontuação final abaixo do saldo mínimo forte; escrita e chat continuam
   adiados. Limite diário ou mensal esgotado não rebaixa tier. Testes do roteador cobrem as
   três situações.
2. Removido `llm.esforco_raciocinio` de `config/limites.yaml`; modelos continuam sendo a fonte
   em `config/modelos.yaml`.
3. Cache de prompt permanece desativado para proteger dados de currículo; a decisão prioriza
   privacidade sobre desconto de tokens e está registrada na ADR 0019, após consulta à
   documentação oficial da OpenAI.
4. Contratos, conformidade, triagem e configuração agora têm implementação em `src/`; os
   módulos do spike reexportam essas implementações sem alterar regras testadas.
5. HTMX está versionado em `src/painel/static/htmx.min.js`, com licença e SHA-256 fixo nos
   testes. O setup não exige Node.js.
6. ADRs 0006 e 0012–0014 foram incluídas no histórico versionado.
7. `.githooks/pre-commit`, ativado por `make setup`, exige `make testes`, `make lint` e
   `make testes-banco` antes de cada commit.

## Fases

### Pré-requisitos da Fase 1, feitos pelo Filipe

- [x] Projeto no Google Cloud com a Gmail API ativada e cliente OAuth do tipo Desktop
- [x] App publicado em produção (Externo, 1 de 100 usuários) para o token não expirar em 7 dias
- [ ] Autorizar a própria conta uma vez no navegador, feito na primeira execução da Fase 1
- [x] JSON do cliente em `segredos/gmail_cliente.json`, chmod 600, fora do git
- [x] `PLEITO_EMAIL_DESTINO` e `OPENAI_API_KEY` preenchidos no `.env`
- [x] Política de privacidade pública em `docs/privacidade.md`, exigida pelo Google
- [ ] Ativar o push do Gmail no iPhone para o rótulo `Candidaturas/Prontas`

### Fase 1: email organizado e resumo diário

**Objetivo:** o Gmail passa a se organizar sozinho e o Filipe recebe o aviso diário.
**O Filipe vê:** as pastas `Candidaturas/*` preenchidas conforme as respostas chegam, e um email
de resumo com o rótulo `Prontas` (mesmo nos dias sem vaga boa, dizendo isso). O painel ganha as
telas Hoje e Candidaturas.
**Criar:** `src/email/` com cliente Gmail (OAuth próprio, escopo mínimo, token no Keychain),
resolução de rótulos por nome, verificação de remetente por domínio exato, classificador por
regra em `config/emails.yaml`, gravação de eventos com auditoria e envio do resumo. Agendamento
por `launchd` com mais de uma janela e `retry_ao_acordar`.
**Regras:** sem IA nesta fase. Lint proíbe exclusão, lixeira, encaminhamento, resposta e envio
fora do módulo de resumo, que só aceita o destino do `.env`.
**Pronta quando:** email falsificado vai para `Suspeitos`, e tentativas de enviar a outro
destinatário ou de excluir falham nos testes.

### Fase 2: currículo confiável e conjunto de avaliação

**Objetivo:** provar que o currículo gerado é seguro e liberar o uso da IA.
**O Filipe vê:** o currículo base decomposto em blocos, o inventário de tecnologias e o resultado
do conjunto de avaliação (20 vagas reais e as armadilhas de injeção).
**Criar:** `conteudo/blocos.yaml`, `conteudo/inventario.yaml`, `templates/cv_*.tex.j2` com
cabeçalho travado, `src/validador/` (uma página, sem tecnologia fora do inventário, sem
travessão) e o conjunto de avaliação.
**Pronta quando:** um tier passa na avaliação e só então recebe `habilitado: true` em
`config/modelos.yaml`, com data e versão do conjunto registradas.

### Fase 3: currículos de família

**O Filipe vê:** as 8 variantes-base com diff em relação ao original, para aprovar uma vez.
**Criar:** `src/gerador/` que preenche slots do template (a IA nunca escreve o `.tex` inteiro).
**Pronta quando:** as variantes compilam em uma página e passam no validador.

### Fase 4: vagas chegando todo dia, sem desperdício

**O Filipe vê:** a lista Hoje com poucas vagas boas e o motivo da nota de cada uma.
**Criar:** migrar o coletor do spike para `src/coletor/` e ligar o funil: duplicata, filtros de
`config/triagem.yaml`, pré-pontuação limitada (`vagas_pre_pontuadas_max`, descrição cortada,
cache por hash), modelo forte só acima de `pre_nota_minima_para_forte`.
**Pronta quando:** um dia sem vaga boa não gera nenhuma chamada forte, provado por teste e pelo
registro de uso.

### Fase 5: edição e aprovação

**O Filipe vê:** a tela de diff por vaga, o histórico de versões e um chat curto para pedir
ajustes (`rodadas_chat_por_vaga`), com o gasto aparecendo no painel.
**Criar:** versionamento de currículo por vaga, chat de edição com o limite de rodadas e a
revisão cruzada para nota quase máxima.

### Fase 6: aplicação assistida (ajustada pela ADR 0011)

**Objetivo:** o roteiro original começava pela Gupy; agora começa por Greenhouse e Ashby.
**O Filipe vê:** o formulário preenchido e a captura de cada etapa, parando antes de enviar. Para
a Gupy, uma pendência manual com link, PDF e respostas prontas para copiar.
**Criar:** `src/aplicador/` em dry-run com banco de respostas e pendências para pergunta nova
(a IA só sugere rascunho, o Filipe aprova). Submit real exige `PLEITO_EGRESS_MODO=submit_real`
mais token, numa vaga que o Filipe escolher.
**Pronta quando:** um submit real autorizado prova que a página de confirmação é detectável.

### Fases 7 a 9

- **7, currículos campeões:** o painel mostra quais versões geraram resposta e usa as melhores como referência.
- **8, cobertura:** outras plataformas, evento no Calendar.
- **9, métricas:** taxa de resposta por família e fonte, e calibração dos pesos.

### Último passo: monitor de disponibilidade

Monitor lógico, não um chamador de retry. Lê o registro de execução e avisa por email se uma
janela do dia não gerou resumo. As janelas ficam em `config/limites.yaml`, fora do horário de uso
do Mac.

## Regras que não mudam

`dados/` e `segredos/` nunca entram em commit. Nenhuma credencial ou dado pessoal em arquivo
versionado, incluindo o email do Filipe. Egress em dry-run por padrão. Sem comentário nem
docstring, sem valor fixo no código. Commit sem assinatura, mensagem no imperativo. Toda mudança
de regra de segurança ou de veredito tem teste que falha sem ela. Uma ADR por decisão nova.
