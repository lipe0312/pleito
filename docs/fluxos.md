# Fluxos de uso e de requisição

Como o pleito funciona do ponto de vista do Filipe (fluxos de uso) e o que cada pedaço chama, em
ordem, com os controles no caminho (fluxos de requisição). Cada fluxo diz se já existe em `src/`
ou qual item do `config/backlog.yaml` o entrega. Controles detalhados em `docs/seguranca.md`;
fluxo de desenvolvimento em `docs/fluxo-de-desenvolvimento.md`.

Legenda: ✅ implementado · ⏳ item pendente (issue) · 👤 manual do Filipe.

## Fluxos de uso

### U1. Dia típico

✅ coleta (F4.1) · ⏳ funil F4.2 (#24), gerador F3.1 (#22), resumo F1.5 (#15), agendamento
F1.7 (#18), painel F1.6 (#17) e F5.2 (#27), aplicador F6.2 (#30) · 👤 launchd M3 (#40), push M2
(#39), submit real M4 (#41).

```mermaid
flowchart TD
  A["06:30 launchd acorda o Mac (pmset)"] --> B["coletor busca vagas nas fontes permitidas"]
  B --> C["deduplica e grava em vagas"]
  C --> D{"filtros de config/triagem.yaml"}
  D -- "fora do perfil" --> X["descartada sem token"]
  D -- "passa" --> E["pré-nota com tier rápido, no máximo vagas_pre_pontuadas_max"]
  E --> F{"pré-nota acima de pre_nota_minima_para_forte?"}
  F -- "não" --> X
  F -- "sim" --> G["nota final e slots do currículo com tier forte"]
  G --> H["validador: uma página, inventário, sem travessão"]
  H -- "recusa" --> Y["versão descartada com motivo"]
  H -- "aprova" --> I["fila de aprovação"]
  I --> J["07:45 email de resumo com o rótulo Candidaturas/Prontas"]
  J --> K["push no iPhone"]
  K --> L["Filipe abre o painel local"]
  L --> M{"diff da versão"}
  M -- "rejeita com motivo" --> Y
  M -- "aprova" --> N{"plataforma"}
  N -- "Greenhouse ou Ashby" --> O["aplicador em dry-run com captura por etapa"]
  N -- "Gupy" --> P["pendência manual com link, PDF e respostas"]
  O --> Q{"Filipe autoriza o submit real?"}
  Q -- "não" --> R["fica pronto, para antes do último clique"]
  Q -- "sim, com token" --> S["envio e captura da confirmação"]
```

Dia sem vaga boa: o resumo sai mesmo assim, dizendo isso, e nenhuma chamada forte é feita.

### U2. Resposta de empresa chega por email

✅ organizador F1.4, classificador F1.2, gravação de evento F1.3 · ⏳ organizador ligado ao
evento F1.9 (#50), tela Candidaturas F1.6 (#17), Calendar F8.1 (#33) · 👤 autorizar Gmail M1 (#38).
Hoje a rodada rotula e arquiva, e o `gravar_evento` existe, mas um não chama o outro: isso é o F1.9.

```mermaid
flowchart TD
  A["email chega na caixa de entrada"] --> B["organizador a cada email_intervalo_min"]
  B --> C["classificador por regra, sem IA"]
  C --> D{"remetente por domínio exato e dmarc=pass?"}
  D -- "não, e imita plataforma" --> S["rótulo Candidaturas/Suspeitos"]
  D -- "sim" --> E{"confiança no limiar?"}
  E -- "não" --> K["rótulo Candidaturas/Classificar"]
  E -- "sim" --> F["rótulo da etapa: Aplicadas, Teste, Entrevista, Oferta, Encerradas"]
  S --> AR["arquivado da caixa de entrada"]
  K --> AR
  F --> AR
  F --> G["evento_email gravado uma vez por mensagem, com auditoria (F1.9 liga)"]
  G --> H{"transição permitida em config/eventos_email.yaml?"}
  H -- "sim" --> I["etapa da vaga muda sozinha"]
  H -- "não" --> K2["fila classificar no painel"]
  I --> J{"virou entrevista?"}
  J -- "sim" --> CAL["evento na agenda do Filipe, sem convidado"]
  P["email pessoal ou alerta do LinkedIn"] --> B
  B -. "não é de candidatura" .-> Z["intocado"]
```

Nada é apagado, encaminhado ou respondido. Link de email nunca é aberto sozinho.

### U3. Vaga da Gupy (sempre manual, ADR 0011)

⏳ F6.3 (#31) · ✅ gatilho de candidatura manual no classificador (F1.2).

```mermaid
flowchart LR
  A["vaga Gupy aprovada"] --> B["pendência no painel: link, PDF, respostas para copiar"]
  B --> C["Filipe aplica no site da Gupy"]
  C --> D["Gupy manda confirmação por email"]
  D --> E["gatilho de candidatura manual reconhecido por regra"]
  E --> F["vaga vira aplicada"]
```

### U4. Ajuste do currículo pelo chat

⏳ F5.1 (#26), F5.3 (#28).

```mermaid
flowchart LR
  A["Filipe pede ajuste, até tamanho_pedido_chat_max_chars"] --> B{"rodadas_chat_por_vaga esgotadas?"}
  B -- "sim" --> X["recusa e sugere editar o bloco"]
  B -- "não" --> C["tier forte devolve slots em JSON"]
  C --> D["validador"]
  D -- "recusa" --> E["mostra o motivo, versão anterior mantida"]
  D -- "aprova" --> F["nova versão com hash, diff no painel, gasto somado"]
```

O pedido do Filipe não vence as regras do guia: tecnologia fora do inventário é recusada.

### U5. Evoluir sem todas as credenciais

```mermaid
flowchart TD
  A["item do backlog"] --> B{"exige credencial para rodar de verdade?"}
  B -- "não" --> C["implementa e prova com testes offline"]
  B -- "sim" --> D["implementa com respx, cliente falso do roteador ou dry_run"]
  D --> E["critérios provados offline, PR e merge"]
  E --> F["item manual M com como fazer e pronto quando"]
  F --> G["Filipe faz quando puder e fecha a issue"]
  G --> H["painel do backlog libera o que dependia dele"]
  C --> E
```

| Credencial ausente | O que continua | O que espera |
| --- | --- | --- |
| refresh token do Gmail (M1) | organizador, eventos, resumo, alertas do LinkedIn nos testes | rodar `make gmail-organizar` de verdade |
| chave da OpenAI ou tier desligado | coleta, filtros, validador, gerador com blocos base, painel | pré-nota, nota final, chat |
| banco parado | `make testes` e lint | `make testes-banco` (Gate B pulado) e o painel com dado |
| token do submit real (M4) | aplicador inteiro em `dry_run` | a prova da página de confirmação |
| escopo do Calendar (M12) | F8.1 nos testes | evento real na agenda |

## Fluxos de requisição

### R1. Autorizar o Gmail (`make gmail-autorizar`) ✅ F1.1, 👤 M1

```mermaid
sequenceDiagram
  autonumber
  actor Filipe
  participant S as scripts/autorizar_gmail.py
  participant L as loopback 127.0.0.1 porta efêmera
  participant G as accounts.google.com
  participant T as oauth2.googleapis.com/token
  participant K as Keychain
  S->>S: lê segredos/gmail_cliente.json, gera PKCE S256 e state
  S->>L: abre servidor só durante a espera
  S->>Filipe: abre o navegador na URL de autorização
  Filipe->>G: consente o escopo gmail.modify
  G->>L: redirect com code e state
  L->>S: consulta do callback
  S->>S: confere state em tempo constante
  S->>T: POST code e code_verifier
  T-->>S: access_token, refresh_token, scope
  S->>S: recusa escopo fora de config/emails.yaml
  S->>K: grava o refresh_token por /usr/bin/security
  Note over S,K: nada vai para arquivo nem para log
```

### R2. Rodada do organizador (`make gmail-organizar`) ✅ F1.4

```mermaid
sequenceDiagram
  autonumber
  participant O as src/email/organizador.py
  participant C as dados/estado/gmail_cursor.json
  participant K as Keychain
  participant T as oauth2.googleapis.com/token
  participant G as gmail.googleapis.com
  O->>C: lê historyId e última leitura
  alt dentro do email_intervalo_min
    O-->>O: adia, sem rede
  else hora de ler
    O->>K: lê refresh_token
    O->>T: POST refresh_token
    T-->>O: access_token em memória
    O->>G: GET labels e resolve Candidaturas/* pelo nome
    O->>G: GET history desde o historyId
    Note over O,G: sem cursor ou historyId expirado usa a consulta inicial in:inbox newer_than:7d
    loop cada mensagem nova
      O->>G: GET messages/id
      O->>O: classifica por regra e confere remetente e dmarc
      O->>G: POST messages/id/modify com o rótulo da etapa e sem INBOX
    end
    O->>C: grava o historyId novo
  end
  Note over O,G: o cliente não tem método de excluir, lixeira, encaminhar, responder ou enviar
```

### R3. Gravar evento de email ✅ F1.3

```mermaid
sequenceDiagram
  autonumber
  participant R as src/email/repositorio.py
  participant DB as Postgres papel do email
  R->>DB: SELECT estado atual da vaga
  R->>R: decide pela política de config/eventos_email.yaml
  R->>DB: INSERT evento_email ON CONFLICT do id da mensagem
  alt mensagem já gravada
    DB-->>R: nada, devolve duplicado
  else nova
    DB-->>R: id do evento
    R->>DB: INSERT auditoria registrar_evento
    alt fila classificar ou suspeito
      R-->>R: para aqui, etapa não muda
    else autenticado, no limiar e transição permitida
      R->>DB: UPDATE vaga estado
      R->>DB: INSERT auditoria mudar_estado
      R->>DB: marca o evento como aplicado e INSERT auditoria
    end
  end
  Note over R,DB: RLS recusa evento não autenticado com confiança máxima e a auditoria só aceita INSERT
```

### R4. Coleta de vagas ✅ F4.1

```mermaid
sequenceDiagram
  autonumber
  participant C as src/coletor
  participant F as fonte permitida
  participant DB as Postgres papel coletor
  C->>C: exige domínio da allowlist de config/fontes.yaml
  C->>F: GET robots.txt
  alt robots proíbe
    C-->>C: NO-GO com evidência, nenhuma vaga
  else permite
    loop cada página, com rps_por_domínio
      C->>F: GET da API sem seguir redirect
      opt redirect
        C->>C: só https, domínio permitido e robots do destino
      end
      F-->>C: vagas em JSON
    end
    C->>C: normaliza e deduplica por hash, fonte e empresa
    C->>DB: INSERT vagas e empresas, só parâmetros
  end
```

### R5. Chamada ao roteador de LLM ✅ roteador, ⏳ uso em F4.2 (#24) e F3.1 (#22), 👤 M7 e M8

```mermaid
sequenceDiagram
  autonumber
  participant M as módulo que pede
  participant R as src/llm/roteador.py
  participant DB as uso_llm e flags
  participant O as api.openai.com/v1/responses
  M->>R: tarefa, tier, prompt com texto externo delimitado, schema, versão
  R->>DB: sistema_ativo ligado?
  R->>R: tier habilitado e tarefa permitida no tier
  R->>R: custo máximo pelo tamanho do prompt e max_tokens_saida
  R->>DB: reserva no teto diário e mensal
  alt saldo do forte abaixo do mínimo
    R->>DB: reserva no rápido, só para pontuacao_final
  end
  R->>O: POST com store false, json_schema strict e nenhuma ferramenta
  O-->>R: texto e tokens
  R->>R: JSON sem chave duplicada, validado em modo estrito
  alt inválido
    R->>DB: finaliza como invalida e propaga o erro
  else válido
    R->>DB: finaliza com o custo real
    R-->>M: objeto validado
  end
```

Teto diário ou mensal esgotado bloqueia a chamada sem fallback (ADR 0018). Cache de prompt
desligado (ADR 0019).

### R6. Requisição ao painel ⏳ F1.8 (#16) e F1.6 (#17)

```mermaid
sequenceDiagram
  autonumber
  actor Filipe
  participant N as navegador
  participant P as FastAPI em 127.0.0.1
  participant DB as Postgres papel do painel
  Filipe->>N: abre http://127.0.0.1:porta do config/painel.yaml
  N->>P: GET com Host
  P->>P: Host é 127.0.0.1 ou localhost na porta certa?
  alt Host estranho
    P-->>N: 400, defesa contra DNS rebinding
  else ok
    P->>DB: conecta só em 127.0.0.1:55432/pleito com o papel do painel
    DB-->>P: linhas que o grant por coluna deixa ver
    P-->>N: HTML com autoescape, CSP estrita e token CSRF
  end
  Filipe->>N: aprova ou rejeita com motivo
  N->>P: POST com token CSRF
  P->>P: sem token, recusa
  P->>DB: grava aprovação e auditoria
```

### R7. Resumo diário ⏳ F1.5 (#15), F1.7 (#18)

```mermaid
sequenceDiagram
  autonumber
  participant L as launchd 07:45
  participant R as src/email/resumo.py
  participant DB as Postgres
  participant G as gmail.googleapis.com
  participant I as iPhone
  L->>R: dispara, com retry_ao_acordar
  R->>DB: lê vagas prontas, eventos e gasto do dia
  R->>R: destino só de PLEITO_EMAIL_DESTINO
  alt destino diferente ou vazio
    R-->>L: falha sem enviar
  else ok
    R->>G: POST messages/send para o próprio Filipe
    R->>G: rótulo Candidaturas/Prontas
    G->>I: push do rótulo
  end
```

É o único módulo com envio, conferido por teste de arquitetura.

### R8. Aplicador em dry-run ✅ spike, ⏳ F6.2 (#30), 👤 M4

```mermaid
sequenceDiagram
  autonumber
  participant A as src/aplicador
  participant B as Playwright com perfil persistente
  participant V as Greenhouse ou Ashby
  participant DB as Postgres papel aplicador
  A->>DB: lê só vaga aprovada com aprovação válida e o hash do PDF
  A->>B: abre com rota que aborta domínio fora da allowlist
  B->>V: carrega o formulário
  loop cada campo
    A->>A: recusa seletor de senha, CPF ou cartão
    A->>B: preenche com o banco de respostas
  end
  A->>B: anexa o PDF da versão aprovada
  A->>DB: grava captura de cada etapa
  opt pergunta nova
    A->>DB: pendência com rascunho, nunca resposta automática
  end
  A->>A: exige PLEITO_EGRESS_MODO submit_real e token de 16 ou mais
  alt dry_run
    A-->>A: para antes do clique
  else autorizado pelo Filipe
    A->>B: clica em enviar e captura a confirmação
  end
  Note over A,V: CAPTCHA nunca é resolvido, vira pendência
```

### R9. Gerar currículo por vaga ⏳ F2.2 (#19), F2.3 (#20), F3.1 (#22), F5.1 (#26)

```mermaid
sequenceDiagram
  autonumber
  participant G as src/gerador
  participant C as dados/conteudo blocos e inventário
  participant R as roteador LLM
  participant T as template travado
  participant V as src/validador
  participant DB as versao_curriculo
  G->>C: blocos e inventário da família
  alt tier desligado
    G->>G: usa os blocos base, sem IA
  else habilitado
    G->>R: escrita_slots com a vaga como dado
    R-->>G: JSON de slots validado
  end
  G->>T: escapa cada slot e preenche
  T->>T: compila com -no-shell-escape
  T->>V: PDF e fonte
  V->>V: uma página, só inventário, sem travessão, comandos na allowlist
  alt recusa
    V-->>G: motivo, versão descartada
  else aprova
    V->>DB: INSERT versão com hash e nível
  end
  Note over T,DB: contato vem do cabeçalho travado e nunca entra em prompt
```

### R10. Sincronizar projetos do GitHub e do portfólio ✅ F2.7, ⏳ tela no F3.4

```mermaid
sequenceDiagram
  autonumber
  participant S as make conteudo-sincronizar
  participant L as leitor (allowlist, robots, limite)
  participant W as GitHub API e portfólio
  participant X as extrator por dicionário
  participant F as dados/conteudo/sugestoes.yaml
  participant A as make conteudo-aprovar
  participant C as blocos.yaml e inventario.yaml
  S->>L: lista repositórios do usuário de config/conteudo.yaml
  L->>L: host fora da allowlist, http puro ou acima do limite: recusa sem requisição
  L->>W: GET sem token, sem seguir redirect
  W-->>S: README e páginas como texto não confiável
  S->>X: linguagens, topics e termos fora de frase de instrução
  X-->>S: tecnologia e evidência, nunca um comando
  S->>F: sugestão pendente com âncora tipo projeto e a URL
  Note over S,C: sincronizar nunca escreve em blocos.yaml nem em inventario.yaml
  A->>F: aprovar com --por grava quem e quando
  A->>C: bloco ou âncora, validado antes de gravar
```
