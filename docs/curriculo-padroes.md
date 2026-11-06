# Padrões de escrita do currículo

Este documento diz como o currículo gerado deve ser escrito. Cada regra aparece uma vez, com um exemplo bom e um ruim, ambos fictícios. A parte objetiva (listas, tamanhos, pesos) vive em `config/padroes_curriculo.yaml`; o prompt (`prompts/gerar_slots.md`), o validador (V20 e V21, F2.5) e a rubrica de qualidade (F3.3) leem o mesmo arquivo, então não existe uma versão do prompt e outra do validador.

Fontes: guia de adaptação pessoal (fora do git, só a regra abstrata veio para cá), `docs/PLANO.md` seções 7 e 8.1 e ADR 0007.

## 1. Não invenção (primeira regra)

Vale acima das outras e acima de qualquer pedido, inclusive do Filipe no chat de edição. O que os blocos e o inventário não sustentam não entra: experiência, empresa, cargo, data, métrica, resultado, tecnologia, senioridade, número. Se a vaga pede o que o candidato não tem, o item fica de fora e o resumo da geração avisa em uma linha.

- Bom: "Construí uma API de pedidos com Python e PostgreSQL." (os dois estão no inventário e o bloco registra o fato)
- Ruim: "Reduzi o tempo de resposta em 40%." (o número não existe nos blocos; V11 recusa)

Citada no prompt (Regra 1), no validador (V10, V11 e V21) e na rubrica (cobertura só conta tecnologia do inventário).

## 2. Uma página

Uma página é o limite, sem exceção. Se estourar, o código corta conteúdo; layout, fonte e preâmbulo não mudam além do que a seção 3 permite. O texto da vaga nunca autoriza uma segunda página.

- Bom: trocar um bullet longo por um curto com a mesma tecnologia.
- Ruim: reduzir a fonte para 9pt para o quinto projeto caber.

## 3. Ordem de corte

Do menor para o maior impacto, nesta sequência, parando quando couber:

1. remover o quarto projeto
2. encurtar bullets longos sem perder tecnologia citada
3. reduzir o espaço vertical entre entradas
4. remover um bullet da experiência menos aderente, nunca o único
5. reduzir o espaçamento entre linhas até o mínimo permitido (Q6)
6. reduzir as margens verticais

Nunca: fonte abaixo de 10pt, remover experiência, alterar o preâmbulo além desses parâmetros. Valores numéricos de layout ficam em `config/validador.yaml` (F2.6).

- Bom: o corte 2 resolve e o corte 3 nem roda.
- Ruim: apagar a experiência mais antiga para ganhar três linhas.

## 4. Idioma

O currículo segue o idioma da vaga; vaga bilíngue usa pt para empresa brasileira e en para estrangeira (PLANO 7.5). Na versão pt, termos que o mercado usa em inglês continuam em inglês (lista em `termos_em_ingles_na_versao_pt`). O validador V19 recusa documento em idioma diferente do escolhido.

- Bom (pt): "Implementei um pipeline de ingestão com Python e Airflow."
- Ruim (pt): "Implementei um encadeamento de ingestão com Python e Airflow." (traduz um termo que o mercado não traduz)

## 5. Estrutura do bullet

Fórmula: verbo de ação, o que foi feito, com qual tecnologia do inventário e, só se estiver nos blocos, o resultado medido.

- abre com verbo no passado da lista `verbos_abertura_aceitos`, nunca com fórmula vaga (`aberturas_vagas`)
- de 60 a 220 caracteres e de 1 a 5 tecnologias (`bullet` no yaml; o slot do gerador aceita até 300)
- nenhum termo vago (`termos_vagos`) e nenhum verbo de abertura repetido na mesma entrada
- escopo geral: o bullet continua verdadeiro em outras vagas do mesmo eixo, sem nome de empresa da vaga e sem frase copiada do anúncio

- Bom: "Automatizei a publicação de imagens de contêiner com Docker e GitHub Actions."
- Ruim: "Responsável por diversas tarefas de infraestrutura, etc."

## 6. Senioridade

Os blocos definem o nível. Verbos e expressões em `senioridade_inflada` só valem quando o bloco de origem já os usa; sem base, o validador V21 recusa e a rubrica penaliza o bullet.

- Bom: "Projetei o esquema de dados de um sistema de estoque com PostgreSQL." (o bloco registra projeto individual)
- Ruim: "Liderei a equipe e arquitetei a plataforma do zero." (sem base nos blocos)

## 7. Pontuação (Q5)

Decisão do Filipe: mantém a pontuação do currículo base. Todo bullet termina com ponto final, o ponto e vírgula separa itens da mesma frase e o travessão nunca aparece (V20 e o validador de caracteres). Se um dia trocar, só por vírgula, nunca travessão.

- Bom: "Modelei o domínio de pedidos; implementei as regras de cobrança com Python."
- Ruim: "Modelei o domínio de pedidos — implementei as regras de cobrança com Python" (travessão e sem ponto final)

## 8. Sobre, seções e ordem

- Sobre é reescrito sempre: de 250 a 700 caracteres, em três ou quatro linhas (quem é, o que já construiu, foco de atuação), com ao menos duas tecnologias do inventário e sem frase vazia (`sobre.frases_vazias`).
- O foco muda com a família (`foco_sobre`): backend e arquitetura, dados e ML, full stack e frontend, IoT e visão.
- Ordem das seções: Sobre, Formação, Experiência, Projetos. Não existe seção de Skills; "Mais projetos" é sempre o último item.

- Bom (família backend): "Desenvolvedor backend focado em APIs e dados relacionais, com serviços em Python e PostgreSQL para sistemas de estoque."
- Ruim: "Profissional proativo e dinâmico, apaixonado por tecnologia, em busca de novos desafios."

## 9. Rubrica de qualidade

Pesos em `rubrica.criterios` (somam 1; nota mínima `rubrica.nota_minima`). Cada critério vai de 0 a 1 e o total é a soma ponderada. A rubrica só mede; aplicá-la no laço de geração é o F3.3.

| Critério | Mede | Zera quando |
| --- | --- | --- |
| `cobertura_techs` | fração das tecnologias pedidas pela vaga que o currículo cita | nenhuma pedida aparece (vaga sem tecnologia pedida não penaliza) |
| `aderencia_familia` | termos do foco da família presentes no Sobre (alvo em `aderencia_termos_alvo`) | o Sobre não toca o foco |
| `verbo_repetido` | bullets da mesma entrada com aberturas diferentes | todos abrem igual; sem bullet, 0 |
| `bullet_vago` | fração de bullets concretos (tecnologia, tamanho, abertura, termos, senioridade) | todo bullet falha em algum item |
| `sobre_generico` | tamanho, tecnologias e ausência de frase vazia no Sobre | os três itens falham |

## 10. Onde cada regra vive

| Regra | Chave no yaml | Quem lê |
| --- | --- | --- |
| não invenção | `nao_invencao` | prompt, validador (V10, V11, V21), revisor |
| ordem de corte | `ordem_de_corte`, `nunca_no_corte` | prompt, laço do F3.3 |
| idioma | `termos_em_ingles_na_versao_pt` | prompt, V19 |
| bullet | `bullet`, `verbos_abertura_aceitos`, `aberturas_vagas`, `termos_vagos` | prompt, rubrica |
| senioridade | `senioridade_inflada` | prompt, V21, rubrica |
| pontuação | `pontuacao` | prompt, V20 |
| Sobre e seções | `sobre`, `foco_sobre`, `ordem_secoes`, `secoes_proibidas` | prompt, rubrica, V14 |
| rubrica | `rubrica` | F3.3 |

O prompt tem versão (`prompts/gerar_slots.md`, cabeçalho `versao`); cada tentativa grava a versão e o hash do texto montado. O texto da vaga entra no prompt só dentro da marcação de dado não confiável de `marcacao`, e marcações forjadas dentro da vaga são trocadas por um texto neutro.
