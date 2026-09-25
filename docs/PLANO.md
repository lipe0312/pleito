# Aplicador de Currículos: documento base de planejamento

> Nome provisório do projeto: `aplicador-curriculos` (ver questão em aberto Q1).
> Status: ideia lapidada, pronta para virar requisitos e implementação incremental.
> Autor da ideia: Filipe Santana. Documento consolidado a partir da conversa de 24/09/2026.
> Revisão 2 (24/09/2026): adicionados chat de edição iterativa (4.6.1 e 7.8), captura de emails de retorno com alertas (4.8.2), currículos campeões (7.9) e estratégia híbrida de modelos (3.3).

---

## 1. Resumo da ideia

Um sistema **local**, rodando no Mac do Filipe, que funciona ao mesmo tempo como:

1. **Buscador de vagas:** todo dia encontra vagas alinhadas ao perfil (estágio e júnior, Brasil e exterior, remoto ou não), usando filtros configuráveis.
2. **Gerador de currículo sob medida:** para cada vaga boa, gera uma variante do currículo em LaTeX seguindo à risca o guia de adaptação, compila, valida e guarda.
3. **Aplicador assistido:** depois da aprovação no painel, tenta enviar a candidatura e devolve as pendências separadas por categoria.
4. **Gestor de vagas:** acompanha todas as candidaturas (inclusive as feitas manualmente, fora do sistema) lendo o Gmail e atualizando o status sozinho.

Princípios que guiam todas as decisões:

- **Segurança em primeiro lugar.** Nenhum texto externo (vaga, email) consegue comandar o sistema. Nenhuma ação crucial acontece sem aprovação no painel.
- **Nada inventado.** Nenhuma tecnologia, empresa, métrica ou data fora das fontes de verdade.
- **Uma página, sempre.** Regra máxima do currículo, acima de qualquer outra regra de layout.
- **Custo mínimo.** Código determinístico faz tudo o que for possível. A LLM só entra onde precisa de julgamento ou escrita.
- **Fluxo contínuo.** O sistema não para se o Filipe não aprovar nada num dia. Só para quando a flag de desligar for ativada.
- **Leve e fácil de manter.** Painel simples, código organizado por módulos com responsabilidades claras.

Importante: o agente que roda no dia a dia **não é o Claude do chat**. É o próprio sistema, que chama uma LLM de forma controlada. O Claude do chat ajuda apenas a projetar e construir.

---

## 2. Arquivos e pastas de referência

### 2.1 Guia de adaptação (fonte de regras de escrita)

```
/Users/mainfilipe/Documents/PESSOAL/DOCUMENTOS/Curriculos/base/guia-adaptacao-curriculo-filipe-santana.md
```

Contém: papel do assistente, regra inviolável de não invenção, fontes a consumir (GitHub e portfólio), cobertura de tecnologias com âncoras, escopos gerais e famílias, o que adaptar por seção, restrições de layout, ordem de corte, idioma e o currículo base em PT e EN.

O guia é o **contrato de escrita**. O sistema carrega o guia no prompt de geração e o validador transforma as regras objetivas dele em checagens automáticas (seção 8).

### 2.2 Pasta do projeto (nova)

Proposta: um repositório novo dentro de `Curriculos/`, ao lado de `base/`.

```
/Users/mainfilipe/Documents/PESSOAL/DOCUMENTOS/Curriculos/
├── base/
│   └── guia-adaptacao-curriculo-filipe-santana.md
│   └── aplicador-curriculos-plano.md
└── aplicador-curriculos/              ← repositório do projeto (nome provisório)
    ├── README.md
    ├── docs/
    │   ├── PLANO.md                   ← documento como esse, porem lapidádo
    │   ├── ameacas.md                 ← modelo de ameaças (seção 10)
    │   └── adr/                       ← registros de decisão (ADR) curtos
    │         └── XXXX_nome_da_decisão.md                  ← https://github.com/adr/madr/blob/4.0.0/template/adr-template-minimal.md?plain=1
    │
    ├── config/
    │   ├── filtros.yaml               ← escopo de busca (seção 6)
    │   ├── fontes.yaml                ← fontes e empresas-alvo
    │   └── limites.yaml               ← limites diários, orçamento de LLM, horários
    ├── conteudo/
    │   ├── blocos.yaml                ← currículo decomposto em blocos (seção 7.2)
    │   ├── inventario.yaml            ← inventário de tecnologias com âncoras
    │   └── guia.md                    ← link ou cópia versionada do guia
    ├── templates/
    │   ├── cv_pt.tex.j2               ← template com preâmbulo e cabeçalho travados
    │   └── cv_en.tex.j2
    ├── src/
    │   ├── coletor/                   ← busca de vagas por fonte
    │   ├── triagem/                   ← filtros, deduplicação, pontuação
    │   ├── gerador/                   ← montagem do currículo (LLM + template)
    │   ├── validador/                 ← compilação e checagens
    │   ├── aplicador/                 ← automação de navegador
    │   ├── email/                     ← leitura, classificação e rótulos do Gmail
    │   ├── llm/                       ← único ponto de acesso à LLM
    │   ├── db/                        ← acesso ao banco, sempre parametrizado
    │   └── painel/                    ← dashboard local
    ├── db/
    │   ├── migrations/
    │   └── policies/                  ← papéis e políticas de RLS
    ├── dados/                         ← fora do git (.gitignore)
    │   ├── familias/<familia>_<idioma>/{cv.tex, cv.pdf, meta.json}
    │   └── vagas/<id_vaga>/{cv.tex, cv.pdf, diff.json, validacao.json}
    ├── segredos/                      ← fora do git, só referências ao Keychain
    └── tests/
```

### Essa estrutura PODE MUDAR a medida em que o projeto cresce

`dados/` e `segredos/` nunca entram no git, porque contêm dados pessoais (telefone no PDF, tokens).

---

## 3. Arquitetura geral

### 3.1 Componentes

| Componente          | Responsabilidade                                                      | Usa LLM?                                           | Tem efeito externo?        |
| ------------------- | --------------------------------------------------------------------- | -------------------------------------------------- | -------------------------- |
| Coletor             | Buscar vagas nas fontes e salvar cruas                                | Não                                                | Só leitura na web          |
| Triagem             | Normalizar, deduplicar, filtrar, pré-pontuar                          | Só na pontuação final dos melhores candidatos      | Não                        |
| Gerador             | Montar a variante do currículo                                        | Sim                                                | Não                        |
| Validador           | Compilar e checar tudo                                                | Não                                                | Não                        |
| Painel              | Mostrar, aprovar, configurar                                          | Não                                                | Não                        |
| Aplicador           | Enviar candidatura aprovada                                           | Não (ver Q7)                                       | **Sim**, só após aprovação |
| Email               | Ler, classificar, rotular, criar e atualizar vagas, detectar retornos | Extração de eventos e casos ambíguos (tier rápido) | Só rótulos no Gmail        |
| Chat de edição      | Receber pedidos de ajuste do Filipe e gerar nova versão do currículo  | Sim (tier forte)                                   | Não                        |
| Roteador de modelos | Escolher o modelo por tarefa, aplicar orçamento, registrar uso        | É o único que chama modelos                        | Não                        |
| Agendador           | Disparar rotinas (launchd no macOS)                                   | Não                                                | Não                        |

Regra estrutural: **quem usa LLM nunca tem efeito externo, e quem tem efeito externo nunca usa LLM.** Isso é a principal defesa contra prompt injection (seção 10).

### 3.2 Stack sugerida (a confirmar, ver Q3 e Q4)

- **Linguagem do pipeline:** Python (Pandas, Playwright, Jinja2, cliente do Gmail).
- **Banco:** PostgreSQL local em Docker, com papéis separados por componente e **Row Level Security**. SQLite não tem RLS, por isso a escolha do Postgres.
- **Painel:** FastAPI + templates Jinja2 + HTMX. Sem build de frontend, pouco JavaScript, fácil de manter. Alternativa: React + Vite, se preferir.
- **LLM:** um único módulo `src/llm/` (o roteador de modelos, seção 3.3) que chama os modelos sem nenhuma ferramenta habilitada (sem acesso a arquivos, rede ou shell). Ver Q2 sobre usar a assinatura (Claude Code em modo não interativo) ou chave de API.
- **Compilação:** `pdflatex` local, sempre sem shell escape.
- **Agendamento:** `launchd` do macOS (roda rotinas pendentes quando o Mac acorda).
- **Segredos:** Keychain do macOS.

### 3.3 Estratégia híbrida de modelos (tiering por custo e raciocínio)

O sistema não trata a "LLM" como uma coisa só. Cada tarefa tem um **tier**, e o roteador (`src/llm/`) escolhe o modelo conforme a configuração em `config/modelos.yaml`.

| Tarefa                                                                        | Tier                                   | Por quê                                                      |
| ----------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------ |
| Sanitização, deduplicação, filtros, pré-pontuação                             | **Sem LLM**                            | Regra e código resolvem                                      |
| Extração de dados da vaga para JSON (nível, modalidade, techs pedidas)        | **Rápido**                             | Extração estruturada, pouco raciocínio                       |
| Pontuação de aderência                                                        | **Rápido**, com escalonamento          | Casos na faixa de corte sobem para o tier forte              |
| Classificação de email ambíguo e extração de eventos (entrevista, data, link) | **Rápido**                             | Tarefa curta e estruturada                                   |
| Escrita da variante de família e da variante da vaga                          | **Forte**                              | Exige julgamento fiel, sem inventar e sem inflar senioridade |
| Chat de edição (seção 7.8)                                                    | **Forte**                              | Mesmo nível de exigência da escrita                          |
| Rascunho de resposta para pergunta nova                                       | **Forte**                              | Texto que vai para recrutador                                |
| Revisão cruzada do currículo (opcional)                                       | **Forte**, de preferência outro modelo | Um segundo olhar independente pega distorções                |

**Modelos são configuração, não código.** Os nomes mudam rápido (vários citados na conversa original, como Claude 3.5 Haiku, Claude 3.5 Sonnet e GPT-4o, já foram substituídos por versões mais novas). Exemplo de configuração, a revisar na hora de implementar:

```yaml
tiers:
  rapido:
    provedor: anthropic
    modelo: claude-haiku-4-5 # exemplo, confirmar versão vigente
    max_tokens_saida: 1500
    orcamento_diario_chamadas: 80
  forte:
    provedor: anthropic
    modelo: claude-sonnet-5 # exemplo, confirmar versão vigente
    max_tokens_saida: 6000
    orcamento_diario_chamadas: 25
escalonamento:
  falha_de_schema_repetida: sobe_para_forte # 2 falhas seguidas no tier rápido
  nota_na_faixa_de_corte: [55, 70] # reavaliada pelo tier forte
fallback:
  forte_indisponivel: adiar_tarefa # nunca cai para o tier rápido na escrita
```

Regras do roteador:

- **Escrita nunca desce de tier.** Se o modelo forte estiver indisponível ou o orçamento acabar, a geração é adiada, não feita com modelo mais fraco.
- **Mesmas defesas para todos os modelos:** nenhum tem ferramentas, todos devolvem JSON validado, todos passam pelos mesmos validadores.
- **Troca de modelo exige teste.** Antes de trocar um modelo na configuração, roda um conjunto fixo de vagas de teste (seção 8.5) e compara os resultados. A troca é registrada na auditoria.
- **Rastreabilidade:** toda chamada registra tarefa, tier, provedor, modelo, versão do prompt, tokens e resultado da validação (tabela `uso_llm`).
- **Privacidade por provedor:** cada provedor usado recebe texto de vagas e trechos do currículo. Usar mais de um provedor aumenta a superfície de exposição de dados. Ver Q21.
- **Assinatura e provedores:** usar a assinatura do Claude (via Claude Code em modo não interativo) só cobre modelos Claude. Modelos de outros provedores exigem chave de API e custo separado. Ver Q2 e Q21.

---

## 4. Fluxo diário completo

### 4.0 Verificação da flag (antes de tudo)

Toda rotina começa lendo a flag `sistema_ativo` no banco.

- Desligada: a rotina registra "pulada, sistema desligado" e encerra imediatamente, sem gastar nada.
- Existe também o modo `somente_acompanhamento`: descoberta e aplicação param, mas a leitura de emails continua atualizando status.
- O aplicador checa a flag de novo **antes de cada vaga**, para que desligar no meio de um lote interrompa o lote.

### 4.1 Descoberta (manhã, ex.: 07:00)

1. Para cada fonte ativa em `fontes.yaml`, o coletor busca vagas novas.
2. Cada vaga é salva crua (texto, URL, fonte, data) na tabela `vagas_brutas`, sem nenhum processamento.
3. Texto passa por **sanitização** (seção 10.2) antes de qualquer outro uso.
4. Respeita limite de requisições por fonte e horário.

### 4.2 Triagem determinística (sem LLM)

1. **Normalização:** título, empresa, local, modalidade, nível, idioma, data de publicação, tipo de contrato.
2. **Deduplicação:** chave = hash de (empresa normalizada + título normalizado + local) mais URL canônica. Vaga já vista nunca é reavaliada.
3. **Filtros eliminatórios** (seção 6.1). Vaga que falha em qualquer um é descartada com o motivo registrado.
4. **Pré-pontuação por palavras-chave:** cruza as techs e termos da vaga com o inventário (seção 7.3). Gera uma nota de 0 a 100.
5. Só as N melhores (ex.: 15) seguem para a pontuação final.

### 4.3 Pontuação final (LLM, só para as N melhores)

A LLM recebe o texto da vaga (marcado como dado não confiável), o inventário e o resumo do perfil, e devolve **JSON estrito**:

```json
{
  "familia": "backend | dados_ml | fullstack | iot_visao",
  "idioma": "pt | en",
  "nota_aderencia": 0,
  "techs_cobertas": ["..."],
  "techs_equivalentes": [{ "pedida": "Kafka", "equivalente": "RabbitMQ" }],
  "requisitos_descobertos": ["..."],
  "alertas": ["possivel_golpe", "exige_visto", "senioridade_acima"],
  "justificativa": "texto curto"
}
```

O JSON é validado contra um schema (valores fora das listas são rejeitados). As melhores até o limite diário (ex.: 6) vão para a geração.

### 4.4 Geração do currículo

1. Escolhe a **família** indicada e o idioma.
2. Se a família já cobre bem a vaga (diferença pequena), **reaproveita o PDF da família**, sem gerar arquivo novo.
3. Se não, a LLM gera uma **variante da vaga** sobre a família (seção 7.4).
4. O código monta o `.tex` a partir do template travado (seção 7.1).
5. O validador compila e roda todas as checagens (seção 8).
6. Se falhar, aplica a ordem de corte automática (seção 7.6) ou devolve o erro para a LLM corrigir, até 3 tentativas.
7. Se ainda falhar, a vaga entra no painel com a pendência `curriculo_invalido`.
8. Grava `cv.tex`, `cv.pdf`, `diff.json` (o que mudou) e `validacao.json` em `dados/vagas/<id>/`.

### 4.5 Painel e resumo do dia (fim da tarde, ex.: 18:00)

1. As vagas geradas aparecem em **"Aguardando aprovação"**, ordenadas por nota.
2. O sistema envia um **email de resumo** para o próprio Filipe (destinatário fixo no código), com a lista curta das vagas e o lembrete para abrir o painel. Ver Q11.
3. Se o Filipe não aprovar nada, as vagas continuam na fila. Vagas que fecharem ou passarem do prazo viram `expirada` e saem da fila sozinhas.

### 4.6 Aprovação (no painel)

Para cada vaga o Filipe pode: **Aprovar**, **Rejeitar** (com motivo opcional, que alimenta ajustes futuros), **Editar e aprovar** (ajustar um bullet na mão e revalidar), **Refazer com IA** (chat de edição, seção 4.6.1) ou **Adiar**.

A aprovação registra: quem, quando, qual versão exata do PDF (hash) e um token de uso único. O aplicador só aceita vagas com aprovação válida e com o hash do PDF batendo. A aprovação vale sempre para **uma versão específica**. Se uma nova versão for gerada depois, a aprovação anterior deixa de valer.

#### 4.6.1 Ciclo de refatoração iterativa (chat de edição)

Quando o currículo gerado não agradar, em vez de editar na mão o Filipe conversa com a IA dentro da tela da vaga:

1. Escreve um pedido, por exemplo: "Dê mais foco no meu projeto de microsserviços" ou "Reduza o tamanho da experiência de pesquisa em IoT".
2. O sistema monta a requisição com: o pedido, o contexto da vaga (dados extraídos, não o texto bruto inteiro quando não for necessário), a versão atual do currículo em slots, os blocos, o inventário e as regras do guia.
3. O tier forte devolve uma **nova versão em slots** (JSON), nunca o `.tex` inteiro.
4. O código monta o `.tex`, compila e roda **todas** as validações da seção 8.
5. O painel mostra a nova versão com dois diffs: **contra a versão anterior** e **contra a família base**, além de uma resposta curta da IA explicando o que mudou.
6. O Filipe pode pedir outro ajuste, voltar para qualquer versão anterior ou aprovar a versão atual.

Detalhes completos, limites e regras de segurança na seção 7.8.

### 4.7 Aplicação

1. Disparada logo após a aprovação (ou em lote, conforme configuração).
2. O aplicador abre um navegador local com perfil persistente, onde o Filipe já está logado nas plataformas. **O sistema nunca guarda nem digita senhas.**
3. Preenche o formulário com dados do banco de respostas aprovado (seção 9) e anexa o PDF aprovado com nome neutro (ex.: `Filipe_Santana_Curriculo.pdf`, sem nome de empresa).
4. Se tudo der certo: status `aplicada`, com captura de tela da confirmação.
5. Se travar: status `pendente` com a categoria (seção 4.9) e o link direto para o Filipe terminar.

### 4.8 Acompanhamento por email (a cada 30 min, ou ao ligar o Mac)

1. Lê emails novos pela API do Gmail (histórico incremental, sem reler tudo).
2. **Classificação por regras primeiro** (remetentes e padrões de assunto conhecidos). LLM só para casos ambíguos, e sem poder de ação.
3. Cada email é associado a uma vaga existente (empresa + título) ou cria uma nova.
4. Atualiza status e aplica o rótulo no Gmail.

#### 4.8.1 Gatilho de candidatura manual

Se o Filipe aplicar em uma vaga por conta própria, fora do sistema, o email de confirmação da plataforma é reconhecido e a vaga é criada automaticamente no painel com `origem = manual_email`. Exemplos de padrões já vistos na caixa dele:

| Plataforma | Remetente               | Padrões de assunto                                                                                               |
| ---------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Gupy       | `no-reply@gupy.com.br`  | "Confirmação de Candidatura", "Recebemos sua candidatura", "Encerramento do processo", "Conclua o Teste Técnico" |
| Sólides    | `system@solides.com`    | "Candidatura efetuada em ...", "Processo seletivo - ..."                                                         |
| InHire     | `*@ses-mail.inhire.app` | "Recebemos sua candidatura", "Feedback processo seletivo"                                                        |

A lista de padrões fica em configuração e cresce com o tempo. Email que parece de candidatura mas não bate em nenhuma regra vai para a fila **"Classificar"** do painel, onde o Filipe confirma com um clique.

Também é possível cadastrar uma vaga manual direto no painel (`origem = manual_painel`). Em vagas manuais, o Filipe pode **anexar o currículo que usou** (ou apontar uma variante existente), para que a vaga também entre no ciclo de currículos campeões (seção 7.9).

#### 4.8.2 Captura de emails de retorno (email grabber) e alertas

Além de confirmar candidaturas, o módulo de email monitora as **respostas das empresas** e transforma cada uma num **evento** ligado à vaga.

**Tipos de evento:**

| Evento               | Exemplos de sinal                                                 | Efeito no status                    | Alerta no painel                                                                  |
| -------------------- | ----------------------------------------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------- |
| `avancou_etapa`      | "você avançou para a próxima etapa"                               | `em_analise`                        | Informativo                                                                       |
| `teste_solicitado`   | "Conclua o Teste Técnico", link de teste                          | `teste` + pendência `teste_tecnico` | Com prazo                                                                         |
| `entrevista_convite` | "gostaríamos de agendar uma entrevista", link de agenda           | `entrevista`                        | **Destaque:** "Você tem um convite de entrevista com a empresa X"                 |
| `entrevista_marcada` | data, hora, link de reunião                                       | `entrevista`                        | **Destaque:** "Você tem uma entrevista marcada com a empresa X em DD/MM às HH:MM" |
| `pedido_documentos`  | pedido de documentos ou dados                                     | sem mudança                         | Pendência `dado_sensivel`                                                         |
| `oferta`             | proposta, "aprovado no processo"                                  | `oferta`                            | **Destaque**                                                                      |
| `rejeicao`           | "optamos por seguir com outro perfil", "encerramento do processo" | `encerrada`                         | Informativo                                                                       |
| `outro`              | não reconhecido                                                   | sem mudança                         | Vai para a fila "Classificar"                                                     |

**Como funciona:**

1. **Regras primeiro:** remetentes conhecidos e padrões de assunto e corpo (a lista cresce com o tempo, como os exemplos reais da seção 4.8.1).
2. **Extração pelo tier rápido** quando a regra não resolve ou quando é preciso extrair dados (data, hora, fuso, link, nome da etapa). Saída em JSON validado:
   ```json
   {
     "evento": "entrevista_marcada",
     "empresa": "...",
     "vaga_ref": "...",
     "data_hora": "2026-10-02T14:00:00-03:00",
     "link_reuniao": "https://...",
     "confianca": 0.0
   }
   ```
3. **Associação à vaga:** por remetente, empresa, título e histórico da conversa (thread do Gmail). Sem correspondência segura, vai para "Classificar".
4. **Atualização de status** respeitando a máquina de estados (seção 4.11). Eventos com confiança baixa **não mudam status sozinhos**, só criam alerta para confirmação.
5. **Alerta no painel** na tela "Hoje", com link para o email original no Gmail.
6. **Agenda (opcional):** para `entrevista_marcada`, o painel oferece "Criar evento no Google Calendar". Só cria depois do clique do Filipe (ação crucial com aprovação).
7. **Currículo campeão:** eventos positivos disparam o ciclo da seção 7.9.

**Segurança específica:**

- Email é texto não confiável: o extrator não tem ferramentas e só devolve JSON.
- **Links nunca são abertos automaticamente.** O painel mostra o domínio do link de forma clara antes do clique.
- **Checagem anti-phishing:** o sistema lê o resultado de autenticação do email (SPF, DKIM, DMARC no cabeçalho `Authentication-Results`) e compara o domínio do remetente com o domínio da plataforma ou da empresa. Falhou, o evento é marcado como **suspeito** e não muda status.
- Pedido de pagamento, de senha ou de dados bancários em email de "recrutador" gera alerta de golpe.

### 4.9 Pendências

Aparecem **somente se existirem**. Sem pendências, o status da vaga é **Completo**.

| Categoria                 | O que o sistema faz      | O que o Filipe faz                                      |
| ------------------------- | ------------------------ | ------------------------------------------------------- |
| `captcha`                 | Para e salva o link      | Resolve e envia                                         |
| `teste_tecnico`           | Registra link e prazo    | Faz o teste                                             |
| `teste_comportamental`    | Registra link e prazo    | Faz o teste (ex.: perfil Sólides)                       |
| `pergunta_nova`           | Rascunha uma resposta    | Aprova, edita ou reescreve, e a resposta entra no banco |
| `dado_sensivel`           | Não preenche             | Preenche CPF, documentos etc.                           |
| `login_expirado`          | Para                     | Entra de novo na plataforma                             |
| `curriculo_invalido`      | Mostra qual check falhou | Edita ou descarta                                       |
| `formulario_desconhecido` | Salva captura de tela    | Aplica manualmente                                      |
| `vaga_encerrada`          | Arquiva sozinho          | Nada                                                    |
| `suspeita_golpe`          | Bloqueia a vaga          | Revisa se quiser                                        |

### 4.10 Rotinas de manutenção

- **Semanal:** atualiza o inventário de tecnologias lendo GitHub e portfólio (seção 7.3). Mudanças no inventário exigem aprovação no painel.
- **Diária:** marca vagas expiradas, aplica a política de retenção de arquivos (seção 7.7), faz backup do banco.

### 4.11 Máquina de estados da vaga

```
descoberta → descartada (motivo)
           → na_fila → curriculo_gerado → aguardando_aprovacao
                                            ├→ rejeitada
                                            ├→ expirada
                                            └→ aprovada → aplicando
                                                            ├→ pendente (categoria) → aplicada
                                                            └→ aplicada
aplicada → em_analise → teste → entrevista → oferta
         ↘ encerrada (a qualquer momento, via email ou manual)
```

Transições são validadas no banco. Uma vaga nunca pula de `aguardando_aprovacao` para `aplicando` sem passar por `aprovada`.

---

## 5. Painel (dashboard local)

Leve, organizado e acessível só em `127.0.0.1`.

### 5.1 Telas

1. **Hoje:** alertas em destaque no topo (entrevistas, convites, ofertas, testes com prazo), depois o resumo em números (novas, aguardando, aplicadas, pendências, respostas recebidas).
2. **Aguardando aprovação:** lista de vagas com nota, família, idioma, modalidade e fonte. Ao abrir uma vaga:
   - Texto da vaga (exibido como texto puro, nunca como HTML).
   - Justificativa da nota e requisitos descobertos.
   - **Prévia do PDF** gerado.
   - **O que mudou em relação à família base**, por seção:
     - Sobre: texto antigo e novo lado a lado, diferenças marcadas.
     - Experiência: bullets que subiram ou desceram e redação alterada.
     - Projetos: quais entraram, saíram e em que ordem.
     - Techs: quais ganharam ou perderam destaque `\tech{}`.
     - Layout: se algum passo da ordem de corte foi aplicado (ex.: linespread reduzido).
   - Resultado de cada check de validação.
   - **Chat de edição** ao lado da prévia, com o histórico de pedidos e a lista de versões (v1, v2, v3...). Cada versão pode ser aberta, comparada ou restaurada.
   - Se a vaga se parece com vagas que já renderam entrevista, mostra qual **currículo campeão** serviu de referência.
   - Botões: Aprovar (esta versão), Rejeitar, Editar e aprovar, Refazer com IA, Adiar.
3. **Candidaturas:** todas as vagas por status, filtros por origem, fonte, família e período. Linha do tempo de cada vaga com os emails associados.
4. **Pendências:** agrupadas por categoria, só aparece se houver.
5. **Classificar:** emails ambíguos esperando confirmação.
6. **Famílias e campeões:** variantes base e currículos campeões, com prévia, histórico de resultados (quantas entrevistas cada um rendeu) e botão para regenerar ou promover (exige aprovação).
7. **Banco de respostas:** perguntas e respostas aprovadas.
8. **Configurações:** filtros, fontes, limites, horários, flag liga/desliga e modo somente acompanhamento.
9. **Auditoria:** log de todas as ações, quem aprovou o quê e quando, incluindo cada pedido do chat de edição, cada chamada de modelo e cada evento de email.
10. **Uso de modelos:** chamadas e tokens por tier e por tarefa, orçamento restante do dia.

### 5.2 Ações que exigem aprovação explícita no painel

- Enviar uma candidatura.
- Aprovar ou regenerar uma variante de família.
- Adicionar ou alterar resposta no banco de respostas.
- Alterar o inventário de tecnologias.
- Alterar filtros, fontes, limites ou a configuração de modelos.
- Excluir arquivos fora da política de retenção automática.
- Promover ou rebaixar um currículo campeão.
- Criar evento de entrevista no Google Calendar.

Pedir uma nova versão no chat de edição **não** exige aprovação (não tem efeito externo), mas conta no orçamento e fica na auditoria.

Ligar e desligar a flag é imediato (é o botão de emergência).

---

## 6. Filtros e escopo de busca

Tudo em `config/filtros.yaml`, editável pelo painel.

### 6.1 Filtros eliminatórios

| Filtro                         | Exemplo de valor                                                 |
| ------------------------------ | ---------------------------------------------------------------- |
| Nível                          | `estagio`, `junior` (exclui pleno, sênior, lead)                 |
| Área / família                 | backend, dados_ml, fullstack, iot_visao                          |
| Modalidade                     | remoto, híbrido, presencial                                      |
| Localização presencial/híbrida | Salvador e região metropolitana                                  |
| Região para remoto             | Brasil, LATAM, global                                            |
| Autorização de trabalho        | exclui vagas que exigem cidadania ou visto que o Filipe não tem  |
| Fuso horário                   | sobreposição mínima de horas com UTC-3                           |
| Idioma da vaga                 | pt, en                                                           |
| Tipo de contrato               | estágio, CLT, PJ, contractor internacional                       |
| Carga horária de estágio       | compatível com a graduação (ex.: até 30h semanais)               |
| Formação exigida               | aceita previsão de formatura em 2027                             |
| Bolsa ou salário mínimo        | valor configurável, opcional                                     |
| Idade da vaga                  | publicada há no máximo X dias                                    |
| Empresas bloqueadas            | lista                                                            |
| Palavras proibidas             | ex.: "sênior", "10+ anos"                                        |
| Sinais de golpe                | pedido de pagamento, taxa de cadastro, contato só por mensageiro |

### 6.2 Fatores de pontuação

| Fator                                                | Peso inicial (a calibrar) |
| ---------------------------------------------------- | ------------------------- |
| Cobertura das techs da vaga pelo inventário          | alto                      |
| Força da âncora (experiência > projeto > disciplina) | médio                     |
| Encaixe na família                                   | médio                     |
| Nível e tipo de vaga                                 | médio                     |
| Modalidade e localização preferidas                  | baixo                     |
| Empresas prioritárias (lista)                        | bônus                     |
| Requisitos descobertos                               | penalidade                |

### 6.3 Limites

- Vagas geradas por dia: 5 a 6 (configurável).
- Máximo de vagas na fila de aprovação: ex.: 30 (as de menor nota saem primeiro).
- Orçamento diário de chamadas à LLM: número máximo de chamadas e de tokens. Ao atingir, a rotina para e registra.

---

## 7. Currículo: famílias, blocos e geração

### 7.1 Template travado

O `.tex` não é escrito inteiro pela LLM. O template Jinja2 contém o **preâmbulo e o cabeçalho travados**, idênticos ao base. A LLM só preenche **espaços controlados** (slots):

- Texto do Sobre.
- Ordem das disciplinas.
- Para cada experiência: ordem e redação dos bullets.
- Escolha e ordem de 3 ou 4 projetos, e redação dos bullets.
- Quais techs levam `\tech{}`.

Vantagens: a LLM não tem como mexer em preâmbulo, contato, datas ou empresas, e o risco de LaTeX malicioso cai muito (seção 10.4). Ver Q8 sobre essa escolha.

### 7.2 Currículo decomposto em blocos (`conteudo/blocos.yaml`)

Cada experiência, projeto e bullet vira um bloco com identificador, fatos imutáveis e variações de redação aprovadas. Exemplo:

```yaml
- id: exp_infocraft
  tipo: experiencia
  imutavel:
    {
      cargo: "Desenvolvedor de Software Estagiário",
      empresa: "Infocraft Consultoria, Tecnologia e Inovação",
      periodo: "2026 -- Presente",
    }
  bullets:
    - id: infocraft_grade
      fato: "módulo de grade horária, heurística + LLM, virou produto comercial"
      techs: [PHP, Laravel, LLM, OpenAI API]
      familias: [backend, dados_ml]
    - id: infocraft_dados
      fato: "camada de dados PostgreSQL multi tenant, views, stored procedures"
      techs: [PostgreSQL, SQL]
      familias: [backend, dados_ml]
```

Projetos seguem o mesmo formato, incluindo **projetos de disciplina** do portfólio. Exemplo: vaga que pede Java pode puxar o projeto da disciplina de POO, se ele existir no portfólio ou no GitHub. A regra continua: só entra o que é real e público.

Projetos também podem ter **variantes de ênfase**, para que a mesma entrada destaque techs diferentes conforme a vaga, sem mudar os fatos. Exemplo: Veridit com ênfase em containerização e gateway (`Docker Compose`, `NGINX`) ou em mensageria e resiliência (`RabbitMQ`, circuit breaker).

### 7.3 Inventário de tecnologias (`conteudo/inventario.yaml`)

Lista fechada de toda tecnologia que pode aparecer em `\tech{}`, cada uma com pelo menos uma âncora:

```yaml
- tech: RabbitMQ
  ancoras:
    [{ tipo: projeto, ref: proj_veridit, fonte: "README microservices_system" }]
- tech: Java
  ancoras:
    [
      {
        tipo: disciplina,
        ref: "POO",
        fonte: "projeto de disciplina no portfólio (a confirmar)",
      },
    ]
```

Também guarda a tabela de **equivalências honestas** do guia (Kubernetes → containerização com Docker Compose, Kafka → mensageria com RabbitMQ, Django → APIs REST com Flask e Laravel, Snowflake/BigQuery → SQL avançado com PostgreSQL).

Atualização semanal a partir de GitHub (`lipe0312`), portfólio e currículo base. Techs novas encontradas ficam como **sugestão** até o Filipe aprovar no painel.

### 7.4 Famílias de currículo

| Família                  | Projeto em destaque    | Foco do Sobre                           |
| ------------------------ | ---------------------- | --------------------------------------- |
| Backend / Arquitetura    | Veridit                | APIs, dados relacionais, microsserviços |
| Dados / ML / IA          | PalmVein               | pipeline de dados, modelagem, XAI       |
| Full Stack / Frontend    | Cycle-Tracker, VisoKey | React, TypeScript, APIs                 |
| IoT / Embarcados / Visão | VisoKey, PalmVein      | edge, MQTT, visão computacional         |

Cada família existe em PT e EN (8 variantes base). São geradas uma vez, aprovadas no painel e **salvas permanentemente**. Regras de escrita da família:

- Escopo geral e reaproveitável, válido para qualquer vaga do mesmo eixo.
- Citar o **máximo de tecnologias possível** sem forçar, sempre ancoradas.
- Nunca nome de empresa de vaga, nunca frase copiada de anúncio.

**Variante da vaga:** um conjunto pequeno de operações sobre a família (trocar ênfase de um projeto, trocar um projeto, reordenar bullets, destacar outra tech, ajustar uma frase do Sobre). A vaga pode influenciar a **escolha de projetos mais ligados ao domínio da empresa** (ex.: fintech → PalmPay e Cycle-Tracker), mas o nome da empresa nunca aparece no documento.

### 7.5 Idioma

- Detectado automaticamente pelo texto da vaga.
- Vaga bilíngue: PT para empresa brasileira, EN para empresa estrangeira.
- Termos que o mercado usa em inglês continuam em inglês na versão PT (Machine Learning, deep learning, full stack, backend, pipeline, embeddings etc.).

### 7.6 Regra de uma página e ordem de corte

**Uma página é a regra máxima.** Os parâmetros de layout podem ser ajustados para caber, dentro de limites definidos. Ordem automática, do menor para o maior impacto:

1. Remover o quarto projeto.
2. Encurtar bullets longos, sem perder tecnologia citada.
3. Reduzir `\vspace{2.5mm}` para `2mm`.
4. Remover um bullet da experiência menos aderente (nunca o único bullet).
5. Reduzir `\linespread` até o mínimo permitido (ver Q6).
6. Reduzir margens verticais de `1.1cm` para `1.0cm`.

Nunca: fonte abaixo de 10pt, remover experiência, alterar preâmbulo além desses parâmetros.

Dado real medido na compilação de teste: a versão PT base sobra só **0,3 linha** livre, e a EN sobra **1,7 linha**. Na prática, quase toda adaptação em PT precisa trocar conteúdo, não somar.

### 7.7 Retenção de arquivos

| Tipo                                             | Retenção                                                                                                                         |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Variantes de família                             | Permanente                                                                                                                       |
| Variante de vaga rejeitada ou expirada           | Apagada após X dias                                                                                                              |
| Variante de vaga **aplicada**                    | Mantida enquanto o processo estiver ativo e mais X dias após encerrar (é o currículo que o recrutador tem em mãos na entrevista) |
| Variante de vaga que ficou quase igual à família | Não gera arquivo, aponta para a família                                                                                          |
| **Currículo campeão ou forte** (seção 7.9)       | **Permanente**, nunca apagado pela rotina de limpeza                                                                             |
| Versões intermediárias do chat de edição         | Apagadas junto com a vaga, exceto a versão aprovada. O histórico de pedidos fica na auditoria                                    |

A rotina de limpeza **sempre consulta a marcação de campeão antes de apagar**, e essa proteção também existe no banco (o papel da rotina de limpeza não tem permissão de excluir registros marcados como campeão).

### 7.8 Chat de edição: regras

**Entrada:** o pedido do Filipe é a única entrada **confiável** do chat. O contexto da vaga continua marcado como não confiável, igual à geração normal.

**O que o chat pode fazer:** tudo que o guia permite: reordenar, reescrever redação mantendo o fato, trocar ênfase de projeto, trocar projeto, mudar destaque de `\tech{}`, encurtar ou ampliar trechos, reescrever o Sobre.

**O que o chat não pode fazer, mesmo que o Filipe peça:** as regras do guia valem acima do pedido. Se o pedido for "adicione Kubernetes" e Kubernetes não está no inventário, a validação V10 barra e a IA responde explicando por que não fez e o que pode fazer no lugar (ex.: destacar containerização com Docker Compose). O caminho para incluir algo novo é **atualizar o inventário ou os blocos** (com aprovação), não forçar pelo chat.

**Versionamento:** cada rodada gera uma versão imutável com: número da versão, pedido, modelo usado, versão do prompt, slots em JSON, hash do PDF, resultado das validações e diffs. Nada é sobrescrito.

**Limites:**

- Máximo de rodadas por vaga (ex.: 8), configurável.
- Cada rodada conta no orçamento do tier forte.
- Pedido com mais de N caracteres é recusado (evita colar textos enormes por engano).

**Aprendizado opcional:** se o mesmo tipo de pedido se repete muito (ex.: "encurte a experiência de IoT" em várias vagas), o painel sugere aplicar o ajuste na **família** inteira, com aprovação. Assim o chat melhora as bases com o tempo, em vez de corrigir sempre o mesmo ponto.

### 7.9 Currículos campeões (feedback loop de sucesso)

**Rastreabilidade de ponta a ponta:** cada candidatura guarda o hash exato do PDF enviado (seção 4.6). Quando chega um email de retorno positivo (seção 4.8.2), o sistema segue a cadeia: **evento → vaga → tentativa de aplicação → versão aprovada → arquivo**. Assim sabe exatamente qual currículo gerou aquele resultado.

**Níveis de marcação:**

| Nível            | Gatilho                                   | Efeito                                                                |
| ---------------- | ----------------------------------------- | --------------------------------------------------------------------- |
| `forte`          | Avançou de etapa ou recebeu teste técnico | Retenção permanente, peso moderado como referência                    |
| `campeao`        | Convite ou entrevista marcada             | Retenção permanente, referência prioritária para a família e o idioma |
| `campeao_oferta` | Oferta recebida                           | Mesmo que campeão, com peso máximo                                    |

A promoção automática acontece para `forte`. Para `campeao`, o sistema sugere e o Filipe confirma no painel, porque é a marcação que mais influencia as próximas gerações. Um campeão pode ser rebaixado manualmente a qualquer momento.

**Como o campeão influencia gerações futuras:**

1. Para uma vaga nova, o sistema procura campeões da **mesma família e idioma** com vagas parecidas (techs pedidas, nível).
2. O campeão entra no prompt de geração como **referência de escolhas**: quais blocos, qual ordem, qual ênfase de projeto, qual redação do Sobre. Isso é passado como slots, não como texto livre.
3. O conteúdo final é **sempre montado a partir dos blocos atuais.** Se o perfil mudou (experiência nova, data atualizada), o campeão não traz informação antiga de volta.
4. A variante gerada continua passando por todas as validações. Ser campeão não dá isenção de nenhuma regra.
5. Quando vários campeões apontam para as mesmas escolhas, o painel sugere **incorporar essas escolhas na família base**, com aprovação.

**Cuidados de interpretação:** uma entrevista não prova que o currículo foi o motivo (a empresa, a vaga e o momento pesam muito). Por isso:

- O peso de um campeão cresce com o número de resultados positivos e com a taxa de sucesso, não com um caso isolado.
- O painel mostra estatísticas simples por família e por campeão: enviadas, avançaram, entrevistas, taxa.
- Candidaturas manuais só entram no ciclo se o currículo usado estiver associado (seção 4.8.1).

---

## 8. Validações

### 8.1 Validação do currículo (código, sem LLM)

| #   | Check                          | Falha se                                                                                                                              |
| --- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| V1  | Compilação                     | `pdflatex` retorna erro                                                                                                               |
| V2  | Página única                   | PDF com mais de 1 página                                                                                                              |
| V3  | Sem estouro de caixa           | `Overfull \hbox` ou `Underfull \hbox` relevante no log                                                                                |
| V4  | Linhas de cabeçalho            | título da experiência ou projeto e a data (`\hfill`) não estão na mesma linha (checado pela posição do texto no PDF)                  |
| V5  | Sobreposição visual            | caixas de texto do PDF se sobrepõem                                                                                                   |
| V6  | Preâmbulo travado              | diferente do template, fora dos parâmetros permitidos da ordem de corte                                                               |
| V7  | Cabeçalho                      | nome, email, telefone, cidade ou links diferentes do base                                                                             |
| V8  | Experiências                   | empresa, cargo, período ou ordem cronológica diferentes                                                                               |
| V9  | Nenhuma experiência sem bullet | alguma experiência vazia                                                                                                              |
| V10 | Inventário                     | alguma `\tech{}` fora do inventário aprovado                                                                                          |
| V11 | Números                        | algum número que não existe nos blocos (ex.: métricas inventadas)                                                                     |
| V12 | Nome da empresa da vaga        | aparece no documento                                                                                                                  |
| V13 | Cópia da vaga                  | trechos longos idênticos ao texto do anúncio                                                                                          |
| V14 | Estrutura                      | seção nova, seção de Skills, negrito fora de `\tech{}`                                                                                |
| V15 | Projetos                       | menos de 3 ou mais de 4, ou "Mais projetos" não é o último                                                                            |
| V16 | Escapes                        | URLs com `_` sem `\_`, títulos com `&` sem `\&`                                                                                       |
| V17 | LaTeX perigoso                 | presença de comandos proibidos (seção 10.4)                                                                                           |
| V18 | Limites de layout              | fonte abaixo de 10pt, linespread ou margem abaixo do mínimo, pode variar para caber uma página                                        |
| V19 | Idioma                         | idioma do documento diferente do idioma escolhido                                                                                     |
| V20 | Estilo de pontuação            | conforme decisão da Q5                                                                                                                |
| V21 | Senioridade inflada            | verbos e expressões proibidas sem base nos blocos ("liderei time", "arquitetei do zero", "led a team", "head of"), lista configurável |
| V22 | Fidelidade aos fatos           | redação de um bullet perde ou troca o fato registrado no bloco (checagem pela revisão cruzada, quando ativa)                          |

### 8.2 Validação da saída da LLM

- JSON contra schema estrito: tipos, tamanhos máximos, listas de valores permitidos.
- IDs de blocos só podem ser IDs existentes em `blocos.yaml`.
- Texto livre (Sobre, redação de bullets) passa pelo escape de LaTeX antes de entrar no template.

### 8.3 Validação da aplicação

- Aprovação válida, token não usado, hash do PDF igual ao aprovado, e a versão aprovada é a versão atual da vaga.
- Domínio da página de candidatura dentro da lista de domínios permitidos da fonte.
- Todos os campos preenchidos vêm do banco de respostas aprovado ou do cadastro fixo.
- Captura de tela da confirmação salva como prova.

### 8.4 Validação do chat de edição

- Pedido com tamanho máximo e sem anexos.
- Saída em slots validada pelo mesmo schema da geração.
- Nova versão passa por todos os checks V1 a V22. Falhou, a IA recebe o erro e tenta de novo (até 2 vezes na mesma rodada). Se ainda falhar, o painel mostra o motivo e mantém a versão anterior.
- Limite de rodadas e orçamento checados antes da chamada.

### 8.5 Validação de eventos de email

- JSON do extrator contra schema (tipo de evento dentro da lista, data válida, link com esquema `https`).
- Autenticação do email (SPF, DKIM, DMARC) e domínio do remetente coerente.
- Transição de status permitida pela máquina de estados.
- Confiança abaixo do limite: vira alerta para confirmação, não muda status.

### 8.6 Conjunto de avaliação (para trocar modelos e prompts com segurança)

Um conjunto fixo de vagas reais anonimizadas (ex.: 20, cobrindo as 4 famílias e os 2 idiomas), mais **vagas armadilha**:

- vaga com tentativa de prompt injection no texto
- vaga que pede tecnologia fora do inventário
- vaga sênior disfarçada de júnior
- email falso de "entrevista" com remetente não autenticado

Toda troca de modelo, de versão de prompt ou de regra passa por esse conjunto antes de entrar em uso. O resultado (taxa de aprovação nas validações, notas, falhas nas armadilhas) fica registrado na auditoria. É isso que garante **adaptabilidade com segurança**: dá para trocar peças sem medo de regressão.

---

## 9. Banco de respostas

Perguntas comuns com respostas aprovadas: disponibilidade, carga horária, nível de inglês, pretensão salarial ou de bolsa, previsão de formatura, links (GitHub, LinkedIn, portfólio), mini carta de apresentação por família e idioma, "por que quer trabalhar aqui" genérica por família.

- Pergunta que já existe (por similaridade): resposta automática.
- Pergunta nova: vira pendência `pergunta_nova` com rascunho. Depois de aprovada, entra no banco.
- Testes técnicos e comportamentais nunca são respondidos pelo sistema.

---

## 10. Segurança

### 10.1 Modelo de ameaças

| Ameaça                                    | Origem                                          | Defesa principal                                                                                               |
| ----------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Prompt injection                          | Texto de vaga, email, README                    | LLM sem ferramentas e sem efeito externo, saída em JSON validado                                               |
| SQL injection                             | Qualquer texto externo                          | Só consultas parametrizadas, papéis com privilégio mínimo, RLS                                                 |
| LaTeX injection                           | Texto que chega ao `.tex`                       | Template travado, escape, lista de comandos proibidos, sem shell escape                                        |
| XSS no painel                             | Texto de vaga exibido                           | Renderização como texto puro, CSP estrita                                                                      |
| Ataque ao painel local                    | Outra página no navegador                       | Só `127.0.0.1`, checagem de Host, token CSRF                                                                   |
| Vaga golpe                                | Anúncio falso                                   | Filtro de sinais de golpe, domínio permitido                                                                   |
| Vazamento de dados                        | Git, logs, painel                               | `dados/` fora do git, sem dados sensíveis no banco, Keychain                                                   |
| Envio indevido                            | Bug ou injeção                                  | Aprovação obrigatória com token e hash                                                                         |
| Phishing disfarçado de recrutador         | Email de retorno falso                          | Checagem SPF/DKIM/DMARC, links nunca abertos sozinhos, evento suspeito não muda status                         |
| Contaminação do ciclo de campeões         | Evento falso marcando um currículo como campeão | Só eventos autenticados promovem, `campeao` exige confirmação no painel                                        |
| Pedido do chat que viola regras           | Pedido do próprio Filipe                        | Regras do guia valem acima do pedido, validadores barram                                                       |
| Exposição de dados a provedores de modelo | Tiering com vários provedores                   | Mínimo de dados por chamada, sem telefone ou dados sensíveis nos prompts, provedores aprovados em configuração |

Nota honesta: não existe forma de impedir que um texto malicioso **tente** uma injeção. O objetivo do desenho é que a tentativa **não tenha efeito**, porque a LLM não tem capacidade nenhuma de agir e toda saída dela é tratada como dado a ser validado.

### 10.2 Prompt injection

1. **Sanitização:** remove HTML, caracteres invisíveis e de largura zero, normaliza Unicode, limita tamanho.
2. **Detecção:** padrões típicos de injeção ("ignore as instruções", "system prompt", pedidos de enviar dados) marcam a vaga como suspeita.
3. **Delimitação:** texto externo sempre entra no prompt dentro de marcação explícita de dado não confiável.
4. **Sem ferramentas:** a chamada à LLM não habilita nenhuma ferramenta, arquivo, rede ou shell.
5. **Saída estruturada:** só JSON validado. Qualquer desvio é descartado.
6. **Separação de poderes:** a LLM nunca decide ações. Ações são código determinístico após aprovação humana.
7. **Mínimo de contexto:** cada chamada recebe só o necessário para a tarefa. O extrator de email não vê o currículo, o escritor do currículo não vê emails. Telefone e dados de contato nunca entram em prompt (o cabeçalho é travado no template).

### 10.3 SQL injection e banco

- Todas as consultas parametrizadas. Regra de lint no CI proíbe SQL montado por concatenação.
- Papéis separados, cada um com o mínimo necessário:

| Papel       | Pode                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------- |
| `coletor`   | inserir em `vagas_brutas`                                                                               |
| `triagem`   | ler `vagas_brutas`, escrever em `vagas` com status até `na_fila`                                        |
| `gerador`   | ler vagas na fila, escrever curriculos e validações                                                     |
| `painel`    | ler tudo, escrever aprovações, configurações e respostas                                                |
| `aplicador` | ler só vagas `aprovada` com aprovação válida, escrever tentativas e pendências                          |
| `email`     | escrever eventos de email, atualizar status pós-aplicação, criar vagas manuais, propor promoção `forte` |
| `chat`      | ler vaga e versões da vaga, escrever novas versões (nunca aprovações)                                   |
| `limpeza`   | excluir arquivos e versões expiradas, **sem permissão sobre registros marcados como campeão ou forte**  |

- RLS por papel garante, no próprio banco, que por exemplo o aplicador **não enxerga** vagas não aprovadas, mesmo com bug no código.
- Transições de status validadas por restrição ou gatilho no banco.
- Backup diário criptografado.

### 10.4 LaTeX

- Compilação sempre com shell escape desligado e acesso a arquivos restrito.
- Comandos proibidos em qualquer slot: `\input`, `\include`, `\write`, `\write18`, `\openin`, `\openout`, `\read`, `\catcode`, `\def`, `\newcommand`, `\immediate`, `\csname`, `\usepackage`, entre outros.
- Todo texto vindo da LLM é escapado (`\`, `{`, `}`, `$`, `&`, `%`, `#`, `_`, `^`, `~`). O único comando que a LLM pode produzir é `\tech{}` com conteúdo do inventário, montado pelo próprio código.

### 10.5 Painel

- Escuta só em `127.0.0.1`.
- Checagem do cabeçalho Host (proteção contra DNS rebinding).
- Token CSRF em toda ação.
- Content Security Policy estrita, sem scripts externos.
- Texto externo sempre renderizado como texto.
- Opcional: PIN local para ações cruciais (ver Q12).

### 10.6 Gmail

- Projeto próprio no Google Cloud com OAuth, escopos mínimos: leitura e alteração de rótulos. Envio só se o resumo diário por email for aprovado (Q11), e com destinatário fixo no código.
- Token guardado no Keychain.
- O sistema nunca apaga, encaminha ou responde email.
- Rótulos em hierarquia: `Candidaturas/Aplicadas`, `Candidaturas/Em andamento`, `Candidaturas/Teste`, `Candidaturas/Entrevista`, `Candidaturas/Encerradas`, `Candidaturas/Classificar`.

### 10.7 Navegador

- Perfil dedicado do Playwright, logado manualmente pelo Filipe.
- Lista de domínios permitidos por fonte.
- Nunca digita senha, nunca cria conta, nunca resolve CAPTCHA.
- LinkedIn: **não automatizar**. Usado só como fonte, via emails de alerta.

---

## 11. Fontes de vagas

| Fonte                    | Como                                          | Observação                                                                                                           |
| ------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Alertas do LinkedIn      | Emails de alerta no Gmail                     | Usa o algoritmo do LinkedIn sem automatizar o site. Filtros de remoto, país e nível configurados no próprio LinkedIn |
| Glassdoor, Catho         | Emails de alerta                              | Mesmo princípio                                                                                                      |
| Gupy                     | Páginas de carreira das empresas              | A investigar: forma de busca e termos de uso (Q14)                                                                   |
| Sólides, InHire          | Páginas públicas de vagas                     | A investigar                                                                                                         |
| Greenhouse, Lever, Ashby | APIs públicas de quadros de vagas por empresa | Principal caminho para empresas estrangeiras que contratam na LATAM                                                  |
| Lista de empresas-alvo   | `fontes.yaml`                                 | Empresas prioritárias, nacionais e internacionais                                                                    |

Regras: respeitar limites de requisição, termos de uso e robots.txt de cada fonte.

---

## 12. Custo e uso da assinatura

- Tiering de modelos (seção 3.3): extração, pontuação e classificação no tier rápido, só escrita e chat no tier forte.
- Filtros e pré-pontuação sem LLM. Só as N melhores recebem avaliação da LLM.
- Campeões e famílias reduzem o trabalho de escrita, porque a geração parte de escolhas já validadas.
- Chat de edição com limite de rodadas por vaga.
- Vaga já vista nunca é reavaliada (deduplicação).
- Famílias geradas uma vez. Variante da vaga é um ajuste pequeno.
- Inventário atualizado uma vez por semana, não a cada vaga.
- Aplicação sem LLM.
- Classificação de email por regras, LLM só em caso ambíguo.
- Orçamento diário com corte automático.
- Flag desligada encerra tudo antes de qualquer custo.

---

## 13. Modelo de dados (rascunho)

| Tabela              | Conteúdo principal                                                                                                              |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `config`            | flag, modo, limites, horários                                                                                                   |
| `fontes`            | fonte, tipo, ativa, domínios permitidos                                                                                         |
| `vagas_brutas`      | texto sanitizado, URL, fonte, data de coleta, hash                                                                              |
| `vagas`             | dados normalizados, status, origem, nota, família, idioma, alertas                                                              |
| `pontuacoes`        | JSON da LLM, versão do prompt                                                                                                   |
| `curriculos`        | vaga, família, caminho, hash do PDF, diff, resultado da validação                                                               |
| `curriculo_versoes` | vaga, número da versão, pedido do chat, modelo, versão do prompt, slots, hash, validação, diff contra anterior e contra família |
| `campeoes`          | currículo, nível (`forte`, `campeao`, `campeao_oferta`), eventos que justificam, confirmado por, data                           |
| `eventos_email`     | email, vaga, tipo de evento, data e hora extraídas, link, autenticação, confiança, confirmado                                   |
| `alertas`           | vaga, tipo, mensagem, lido em                                                                                                   |
| `modelos_config`    | tier, provedor, modelo, versão, ativo desde, resultado da avaliação                                                             |
| `familias`          | família, idioma, versão, aprovada em                                                                                            |
| `aprovacoes`        | vaga, hash aprovado, token, usado em                                                                                            |
| `tentativas`        | vaga, início, fim, resultado, captura                                                                                           |
| `pendencias`        | vaga, categoria, detalhe, resolvida em                                                                                          |
| `emails`            | id do Gmail, vaga, classificação, data (sem corpo completo, só o necessário)                                                    |
| `respostas`         | pergunta normalizada, resposta, aprovada em                                                                                     |
| `inventario`        | tech, âncoras, status (aprovada ou sugerida)                                                                                    |
| `auditoria`         | ação, ator, alvo, data                                                                                                          |
| `uso_llm`           | rotina, tarefa, tier, provedor, modelo, versão do prompt, tokens, resultado, data                                               |

---

## 14. Roteiro de implementação incremental

| Fase | Entrega                                                                                                                                                      | Valor                                                         |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| 0    | Repositório, banco com papéis e RLS, painel vazio, flag, auditoria, roteador de modelos com `modelos.yaml` e registro de uso                                 | Fundação segura                                               |
| 1    | Gestor de vagas: leitura do Gmail, gatilho de candidatura manual, **captura de emails de retorno com eventos e alertas**, rótulos, telas Hoje e Candidaturas | Organiza o que já existe, alerta de entrevista desde o início |
| 2    | Blocos, inventário, template travado, validador completo, conjunto de avaliação inicial                                                                      | Currículo confiável                                           |
| 3    | Geração das 8 variantes de família com aprovação                                                                                                             | Currículos prontos para uso manual                            |
| 4    | Coletor (alertas por email + Greenhouse, Lever, Ashby) e triagem com tier rápido                                                                             | Vagas chegando todo dia                                       |
| 5    | Pontuação e variante por vaga, tela de diff, **versionamento e chat de edição**                                                                              | Fluxo de aprovação completo                                   |
| 6    | Aplicador na Gupy com banco de respostas e pendências, hash da versão enviada                                                                                | Primeira aplicação assistida                                  |
| 7    | **Currículos campeões**: rastreio evento → versão, promoção, retenção protegida, uso como referência                                                         | Ciclo de aprendizado com o mercado                            |
| 8    | Outras plataformas, resumo diário, evento no Calendar                                                                                                        | Cobertura maior                                               |
| 9    | Métricas (taxa de resposta por família, fonte e campeão) e calibração de pesos                                                                               | Melhoria contínua                                             |

Cada fase termina com testes, incluindo testes de ataque (vaga com tentativa de injeção, texto com LaTeX malicioso, SQL em campos).

---

## 15. Achados técnicos já verificados

Compilação de teste das duas versões base do guia:

- **PT:** compila, 1 página, sem estouro de caixa. Sobra 0,3 linha livre.
- **EN:** não compilava. Dois problemas no arquivo:
  - `\tech{face_recognition}` sem escape. Correto: `\tech{face\_recognition}`.
  - Linha `## \end{document}` com resto de markdown. Correto: `\end{document}`.
  - Após correção: 1 página, sem estouro, 1,7 linha livre.
- PT usa `\linespread{0.90}` e EN usa `0.95`, ambos definidos pelo Filipe.
- O ambiente precisou do pacote de idioma português do LaTeX (`texlive-lang-portuguese`) para compilar a versão PT. Incluir na lista de dependências.

### 15.1 Ajustes pendentes no guia (versão 2)

- Corrigir os dois erros da versão EN.
- Seção 7: substituir "jamais mexa no linespread" pela nova regra (uma página é a regra máxima, linespread ajustável dentro de limites, seção 7.6).
- Seção 8: incluir o formato de saída do pipeline (JSON de slots em vez de bloco de código no chat).
- Seção 9: trocar "na dúvida, pergunte" pela regra automática de idioma (seção 7.5).
- Seção 3: indicar que no pipeline a leitura do GitHub vem do inventário semanal.
- Seção 6: incluir projetos de disciplina como opção de projeto (ex.: POO em Java).

---

## 16. Questões em aberto

| #   | Questão                               | Opções ou sugestão                                                                                                                                                                                                                                                                                                                       |
| --- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | Nome definitivo do projeto e da pasta | `aplicador-curriculos` é provisório (SUGIRA UM NOME DE MERCADO MELHOR )                                                                                                                                                                                                                                                                  |
| Q2  | Como chamar a LLM                     | Claude Code em modo não interativo usando a assinatura, com todas as ferramentas desligadas, ou chave de API com custo separado. (O que ficar com menos custo, atualmente ja pago claude mas estou disposto a carregar a api da OpenAI que já tenho conta). Verificar limites e termos de uso da assinatura para uso automatizado        |
| Q3  | Stack do painel                       | FastAPI + HTMX (mais leve) ou React + Vite (mais familiar) (Foco no mais leve, o painel é simles e direto, sem rebuscagem, mas deve ser manutenivel e facilmente migrável se escalar)                                                                                                                                                    |
| Q4  | Banco                                 | Postgres em Docker (tem RLS) é a sugestão. Confirmar se aceita rodar Docker no Mac, sim pode ser, gostaria de configurar esse banco no PgAdmin pessoa também, isso envolve alteração manual? da pra fazer pelo terminal né?                                                                                                              |
| Q5  | Ponto e vírgula no currículo          | Manter como no base ou trocar por vírgula também no currículo , manter a base do currículo original. Se for trovar, apenas por vírgula, nunca travessão                                                                                                                                                                                  |
| Q6  | Limites de layout                     | Linespread mínimo por idioma (ex.: PT 0,88, EN 0,90) e margem mínima, alterável se necessário, para caber em uma página                                                                                                                                                                                                                  |
| Q7  | Aplicador com ou sem LLM              | Sem LLM é mais seguro. Formulários desconhecidos viram pendência. LLM poderia só sugerir mapeamento de campos, sem agir, sugerir o "Personalize candidatura e afins também , sendo um second step dessa aplicação que gerou pendencia, ou seja , aprovo um texto da ia para nova pendencia se for esse caso de uso.                      |
| Q8  | Slots ou `.tex` inteiro               | Slots (recomendado, mais seguro) ou LLM escreve o `.tex` inteiro e o validador compara com o base, slots, vamos criar as partes do tex que ele pode alterar e as que ele não pode, economiza token tempo e mantem padrão.                                                                                                                |
| Q9  | Projetos de disciplina                | Listar quais existem no portfólio e GitHub (POO em Java, outros) e se os repositórios são públicos. Acesse https://filipe-santana-portfolio.vercel.app/ e consuma os projetos lá, alem de https://github.com/lipe0312 como meu github (isso deve ser armazenado em banco na minha opnião, não deve ficar solto no repositório não )      |
| Q10 | Horários e limites                    | Horário da descoberta, do resumo, quantas vagas por dia, tamanho máximo da fila. descubra o melhor, quero que depois das 8 já esteja pronto, e me avis no email.                                                                                                                                                                         |
| Q11 | Resumo diário por email               | Exige permissão de envio no Gmail. Alternativa: notificação do macOS e só o painel Pode ser os dois, darei permissão do email, ainda mais se der pra usar o claude com connectors para isso ( criar uma skill), mas o meu objetivo é fazer sem isso.                                                                                     |
| Q12 | PIN local no painel                   | Sem PIN (só localhost) ou PIN para ações cruciais o que for melhor                                                                                                                                                                                                                                                                       |
| Q13 | Empresas-alvo                         | Lista inicial de empresas nacionais e internacionais (LATAM, estágio) Não tenho, deve ser um parametro configurável no painel e salvo em banco. Sem empresa configurada , pega qualquer uma, com empresa configurada, sempre sugere de empresas parecidas ou se não achar vaga da empresa simplesmente atua normal ( melhore esse fluxo) |
| Q14 | Gupy e Sólides                        | Como descobrir vagas nessas plataformas respeitando termos de uso isso tem que ser o primeiro teste, ver se é viável                                                                                                                                                                                                                     |
| Q15 | Retenção                              | Quantos dias para apagar variantes rejeitadas e encerradas Decida o melhor                                                                                                                                                                                                                                                               |
| Q16 | Carta de apresentação                 | Gerar por vaga ou usar só as do banco de respostas tem um padrão no banco e se for solicitada ( virear pendencia ) ser customizada baseado na candidatura, sem forçar claro.                                                                                                                                                             |
| Q17 | Mac desligado                         | Aceitar que rotinas rodem quando o Mac acordar, ou mover descoberta e email para um servidor pessoal no futuro pensar em servidor pessoal no futuro , com horarios de retry                                                                                                                                                              |
| Q18 | Backup                                | Onde guardar o backup criptografado (disco externo, Drive) disco por enquanto                                                                                                                                                                                                                                                            |
| Q19 | Banco de respostas inicial            | Levantar pretensão, disponibilidade, carga horária e demais respostas padrão SIm                                                                                                                                                                                                                                                         |
| Q20 | Critério de "diferença pequena"       | Quando a variante da vaga reaproveita a família sem gerar arquivo Quanto for do mesmo tipo de aplicação , com poucas mudanças na stack, pode até reutilizar currículo se for viável                                                                                                                                                      |
| Q21 | Provedores de modelo                  | Só Claude (um provedor, cabe na assinatura, menos exposição de dados) ou misto (Claude + outros via API). Recomendação inicial: um provedor só, com o roteador pronto para trocar já falado, se der usar claude como inscrição, mas sem problema de usar openAI                                                                          |
| Q22 | Modelos de cada tier                  | Escolher e testar no conjunto de avaliação na hora de implementar, porque as versões mudam rápido SIm                                                                                                                                                                                                                                    |
| Q23 | Revisão cruzada ativa                 | Sempre, só para vagas de nota alta, ou só quando o chat foi usado Vagas de nota quase máxima ou/e quando o chat foi usado                                                                                                                                                                                                                |
| Q24 | Limites do chat                       | Rodadas por vaga e tamanho máximo do pedido deve existir baseado no usage ou no quanto eu já usei( se for via api)                                                                                                                                                                                                                       |
| Q25 | Promoção de campeão                   | Automática para `forte` e com confirmação para `campeao` (proposta atual), ou tudo com confirmação . ta bom com niveis de curriculo assim                                                                                                                                                                                                |
| Q26 | Limiar de confiança dos eventos       | A partir de qual confiança um evento de email muda status sozinho > dedecida seja rigoroso                                                                                                                                                                                                                                               |
| Q27 | Emails de retorno fora do padrão      | Recrutadores que respondem de email pessoal ou de domínio diferente da empresa: aceitar via confirmação manual na fila "Classificar" Sim aceitar isso                                                                                                                                                                                    |

---

## 17. O que ainda pode ser lapidado

- **Aprendizado com rejeições:** usar os motivos de rejeição no painel e as respostas negativas por email para recalibrar pesos e filtros.
- **Métricas por família:** qual família e qual fonte geram mais respostas positivas.
- **Preparação para entrevista:** ao mudar para `entrevista`, gerar um resumo da vaga, do currículo enviado e das techs citadas.
- **Prazos de teste e entrevista:** lembretes antes do vencimento de testes técnicos e antes de entrevistas marcadas.
- **Campeões por tipo de empresa:** separar referências por porte ou setor (startup, banco, consultoria), não só por família.
- **Atalhos de pedido no chat:** botões prontos para os pedidos mais frequentes ("encurtar", "mais foco em backend"), que geram menos tokens e respostas mais previsíveis.
- **Comparação de modelos em produção:** rodar, de vez em quando, a mesma vaga em dois modelos e mostrar lado a lado no painel, para decidir trocas com dados reais.
- **Detecção de vaga repetida entre fontes:** a mesma vaga no LinkedIn e na Gupy.
- **Modo férias:** pausa programada por datas.
- **Exportação:** relatório mensal das candidaturas.

---

## 18. Revisão 3: fluxo consolidado e ajustes finais

> Revisão 3 (24/09/2026): fluxo consolidado em nível de sistema e de usuário, textos de candidatura na etapa de escrita, autofill de diversidade, confirmação de candidatura após pendência, currículos campeões no plural e organização do Gmail com arquivamento.

### 18.1 Fluxo em nível de sistema

1. **Coleta (manhã, horário fixo definido no painel):** o script busca vagas nas fontes ativas usando os filtros do painel. Se a flag estiver desligada, nada roda.
2. **Filtro determinístico (sem LLM):** normalização, deduplicação, filtros eliminatórios e pré-nota por palavras-chave.
3. **Auditoria com o tier rápido:** avalia as ~15 melhores da pré-nota (não só 6), para que uma vaga boa com pré-nota mediana ainda tenha chance. Escolhe até 6. Se só 3 passarem da nota mínima, entram só 3. O sistema nunca completa a lista com vaga ruim.
4. **Escrita com o tier forte:** escolhe a família, reaproveita um currículo existente quando a vaga é parecida (o mesmo currículo pode servir para várias vagas) e só gera uma variante nova quando precisa. Compila e valida (V1 a V22), refazendo se falhar.
5. **Textos de candidatura na mesma etapa:** o "sobre mim", o "personalize sua candidatura" da Gupy e as cartas curtas são escritos aqui pelo tier forte, junto com o currículo, e aparecem no painel para aprovação. O pacote aprovado é: currículo + textos + respostas previstas.
6. **Aprovação no painel:** o Filipe aprova, recusa ou pede ajustes no chat de edição (nova versão, nova validação).
7. **Aplicação sem LLM:** o robô usa apenas autofill padrão, banco de respostas e textos já aprovados, e anexa o PDF aprovado (hash conferido).
8. **Pendência com motivo:** tudo o que o robô não consegue preencher vira pendência com categoria e explicação legível. Exemplo: "a pergunta 'Qual sua experiência com Kotlin?' não existe no banco de respostas".
9. **Confirmação da candidatura:** toda candidatura, automática ou concluída após pendência, passa pela confirmação da seção 18.4.
10. **Acompanhamento:** a vaga vai para "Em aberto". Emails são rotulados e arquivados (seção 18.6). Cada resposta nova atualiza o status e move o email para o marcador certo.

### 18.2 Fluxo em nível do usuário

1. **Manhã:** o Filipe não faz nada. O sistema trabalha sozinho.
2. **Fim da tarde:** chega um email curto de resumo ("6 vagas prontas, 1 resposta nova").
3. **À noite, no painel:**
   - No topo, os alertas ("Entrevista marcada com a empresa X, dia 02/10 às 14h").
   - Até 6 vagas, cada uma com nota, motivo, currículo (pode se repetir entre vagas parecidas), o que mudou e os textos de candidatura.
4. **Decisão:** aprova as que gostou, recusa as outras e, se quiser, pede ajuste no chat antes de aprovar.
5. **Aplicação:** em poucos minutos cada vaga aprovada aparece como **Aplicada (confirmada)**, **Aplicada (aguardando confirmação)** ou **Pendente**.
6. **Pendências:** só aparecem se existirem, cada uma com o motivo. O Filipe resolve (responde a pergunta, faz o CAPTCHA, conclui o teste) e recebe o **cartão de confirmação** da vaga (seção 18.4).
7. **Depois disso:** a vaga fica em "Em aberto" com o histórico completo. No Gmail, os emails dela ficam no marcador certo, fora da caixa de entrada.
8. **Quando a empresa responde:** o email vai sozinho para o marcador da etapa, o status muda no painel, alertas importantes aparecem no topo e, se o currículo teve bom resultado, ele entra no grupo de campeões (seção 18.5).
9. **Dias sem acesso:** as vagas ficam na fila, as expiradas saem sozinhas e os emails continuam sendo organizados.

### 18.3 Autofill de diversidade (dados sensíveis)

Campos como gênero, raça ou cor, PcD, orientação e similares são **dados pessoais sensíveis pela LGPD**. Regras:

- **Configuração campo por campo** no painel. Cada campo tem a opção "prefiro não informar", que é o padrão até o Filipe escolher outra coisa.
- **O sistema nunca deduz nenhum desses dados.** Só usa o que foi configurado explicitamente.
- **Armazenamento criptografado** no banco. A chave fica no Keychain do macOS, nunca no repositório.
- **Acesso restrito por RLS:** só o papel `aplicador` lê esses campos, e só no momento de preencher. O papel `painel` pode editar, mas a tela mostra os valores mascarados até um clique de revelar.
- **Nunca enviados a nenhum modelo de IA**, nunca em logs, email de resumo, auditoria ou diffs. A auditoria registra apenas "campo X preenchido na vaga Y".
- **Capturas de tela:** a captura de confirmação é feita depois do envio. Se a tela ainda mostrar esses campos, a área é borrada ou a captura é pulada.
- **Mapeamento de opções:** cada plataforma usa rótulos diferentes ("Parda", "Pardo(a)"). O mapeamento fica em configuração. Se a opção não for encontrada com segurança, o robô escolhe "prefiro não informar" quando existir. Se não existir, vira pendência `dado_sensivel`, sem chute.
- **Edição e exclusão** só pelo painel, com registro na auditoria.

### 18.4 Confirmação da candidatura

Uma candidatura só é considerada concluída depois de confirmada. Isso vale para as automáticas e para as concluídas pelo Filipe após uma pendência.

**Estados:**

- `aplicada_aguardando_confirmacao`: o envio foi feito (pelo robô ou marcado como concluído pelo Filipe), mas ainda sem prova.
- `aplicada_confirmada`: há prova de envio.
- `aplicada_nao_confirmada`: passou o prazo (ex.: 24h) sem prova. Gera alerta para o Filipe verificar.

**Provas aceitas (qualquer uma):**

1. Página de confirmação da plataforma detectada pelo robô, com captura de tela.
2. Email de confirmação da plataforma ("Recebemos sua candidatura", "Candidatura efetuada") associado à vaga.
3. Confirmação manual do Filipe no painel ("confirmo que enviei"), registrada na auditoria como prova de nível mais fraco.

**Cartão de confirmação** mostrado no painel ao concluir (e salvo no histórico da vaga):

- Empresa, título da vaga, link, fonte e plataforma.
- Data e hora do envio.
- Versão exata do currículo enviada (número da versão, hash, link para o PDF).
- Textos de candidatura enviados.
- Respostas usadas do banco de respostas e respostas novas criadas na pendência.
- Pendências que existiram e como foram resolvidas.
- Tipo de prova de envio.
- Próximo passo esperado (ex.: "aguardando retorno", "teste até 30/09").

### 18.5 Currículos campeões (no plural)

Não existe "o" campeão. Existe um **grupo de campeões**: todos os currículos que deram certo, ou seja, que passaram pelo filtro automático (ATS) ou chamaram a atenção de um recrutador.

**Sinais de sucesso** (o ATS não é visível diretamente, então o sucesso é inferido por eventos autenticados):

| Sinal               | Evento que indica                                                               | Nível            |
| ------------------- | ------------------------------------------------------------------------------- | ---------------- |
| Passou no ATS       | avançou de etapa, recebeu teste, qualquer contato humano após a triagem inicial | `forte`          |
| Chamou o recrutador | contato direto de recrutador, convite ou entrevista marcada                     | `campeao`        |
| Resultado final     | oferta                                                                          | `campeao_oferta` |

**Como o grupo funciona:**

- Cada currículo pode acumular vários sinais em várias vagas. O painel mostra, por currículo: enviadas, passaram no ATS, contatos de recrutador, entrevistas, ofertas e taxa de sucesso.
- O grupo é organizado por **família e idioma**, e dentro de cada um por semelhança de vaga (techs pedidas, nível, setor).
- Na geração de uma vaga nova, entram como referência os **2 ou 3 campeões mais parecidos**, com peso proporcional à taxa de sucesso, não só um.
- Todos os campeões têm **retenção permanente**, protegida no banco contra a rotina de limpeza.
- Promoção a `forte` é automática. Promoção a `campeao` e `campeao_oferta` é sugerida e confirmada no painel. Qualquer campeão pode ser rebaixado manualmente.
- Escolhas que se repetem entre vários campeões (mesma ordem de projetos, mesma ênfase) viram sugestão de atualização da família base, com aprovação.

### 18.6 Organização do Gmail (marcar e arquivar)

- **Todo email de candidatura é rotulado e retirado da caixa de entrada** (arquivado), para manter a caixa limpa. O email continua acessível no marcador e no painel.
- **Marcadores por etapa:** `Candidaturas/Aplicadas`, `Candidaturas/Em andamento`, `Candidaturas/Teste`, `Candidaturas/Entrevista`, `Candidaturas/Oferta`, `Candidaturas/Encerradas`, `Candidaturas/Classificar`, `Candidaturas/Suspeitos`.
- **Quando o status muda**, o marcador da etapa anterior é removido e o novo é aplicado, e o email mais recente puxa a conversa inteira (thread) junto.
- **Sem perder nada importante:** entrevista, oferta e teste com prazo aparecem como alerta em destaque no painel e no resumo diário, mesmo arquivados. Opção nas configurações para manter esses tipos também na caixa de entrada.
- **Emails suspeitos** (falha em SPF, DKIM ou DMARC, ou sinais de golpe) vão para `Candidaturas/Suspeitos`, sem mudar status.
- **Permissões:** o escopo do Gmail precisa permitir alterar marcadores (o que inclui arquivar). O código **nunca** chama exclusão, lixeira, encaminhamento ou resposta, e uma regra de lint no repositório bloqueia essas chamadas.
- Toda alteração de marcador fica na auditoria (email, marcador anterior, marcador novo, motivo).

### 18.7 Questões em aberto adicionadas

| #   | Questão                                               | Opções ou sugestão                                                          |
| --- | ----------------------------------------------------- | --------------------------------------------------------------------------- |
| Q28 | Prazo para `aplicada_nao_confirmada`                  | 24h, 48h ou por plataforma                                                  |
| Q29 | Quantos campeões entram como referência por geração   | 2 ou 3, com limite de tokens                                                |
| Q30 | Manter entrevista e oferta também na caixa de entrada | Desligado por padrão (tudo arquivado) ou ligado                             |
| Q31 | Campos de diversidade a suportar                      | Gênero, raça ou cor, PcD, orientação, outros que aparecerem nas plataformas |
| Q32 | Prova manual de envio                                 | Aceitar sempre ou só quando não houver email de confirmação após o prazo    |
