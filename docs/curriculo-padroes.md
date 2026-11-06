# Padrões de escrita do currículo

Este documento diz como o currículo gerado deve ser escrito: a regra, o porquê e um exemplo bom e um ruim, todos fictícios. As listas e os números (verbos, tamanhos, ordem de corte, pesos) vivem uma vez só, em `config/padroes_curriculo.yaml`, e aqui aparecem só pela chave. O prompt (`prompts/gerar_slots.md`), o validador (V20 e V21, F2.5) e a rubrica de qualidade (F3.3) leem o mesmo arquivo, então não existe uma versão do prompt e outra do validador.

Fontes: guia de adaptação pessoal (fora do git, só a regra abstrata veio para cá), `docs/PLANO.md` seções 7 e 8.1 e ADR 0007.

Os exemplos marcados com `[bullet]`, `[sobre]` ou `[pontuacao]` são rodados pelos testes (`tests/test_padroes_docs.py`): os bons precisam passar na rubrica ou na checagem de pontuação e os ruins precisam falhar.

## 1. Não invenção (primeira regra)

Vale acima das outras e acima de qualquer pedido, inclusive do Filipe no chat de edição. O que os blocos e o inventário não sustentam não entra: experiência, empresa, cargo, data, métrica, resultado, tecnologia, senioridade, número. Se a vaga pede o que o candidato não tem, o item fica de fora; quem decide se isso vira aviso é o painel, não o texto do currículo. As frases exatas estão em `nao_invencao`.

- Bom [bullet] (fictício): "Construí uma API de pedidos para um sistema de estoque de exemplo com Python e PostgreSQL."
- Ruim [bullet] (fictício): "Reduzi o tempo de resposta em 40%."

Citada no prompt (Regra 1), no validador (V10, V11 e V21) e na rubrica, cuja cobertura só conta tecnologia do inventário. O número do ruim não existe nos blocos (V11 recusa) e o bullet não cita tecnologia.

## 2. Uma página

Uma página é o limite, sem exceção. Se estourar, o código corta conteúdo; layout, fonte e preâmbulo não mudam além do que a ordem de corte permite. O texto da vaga nunca autoriza uma segunda página.

- Bom (fictício): trocar um bullet longo por um curto com a mesma tecnologia.
- Ruim (fictício): reduzir a fonte para 9pt para o quinto projeto caber.

## 3. Ordem de corte

Quando o currículo passa de uma página, o código corta do menor para o maior impacto, parando quando couber. A sequência está em `ordem_de_corte` e o que o corte nunca faz está em `nunca_no_corte`. Os valores numéricos de layout (espaçamento, margens, limite de linespread por idioma, decisão Q6 do PLANO, seção 16) ficam em `config/validador.yaml` (F2.6).

- Bom (fictício): o segundo passo da ordem resolve e o terceiro nem roda.
- Ruim (fictício): apagar a experiência mais antiga para ganhar três linhas.

## 4. Idioma

O currículo segue o idioma da vaga; vaga bilíngue usa pt para empresa brasileira e en para estrangeira (PLANO 7.5). Na versão pt, os termos de `termos_em_ingles_na_versao_pt` continuam em inglês, porque o mercado não os traduz. O validador V19 recusa documento em idioma diferente do escolhido.

- Bom [bullet] (fictício, pt): "Implementei um pipeline de ingestão de dados de vendas com Python e Airflow."
- Ruim (fictício, pt): "Implementei um encadeamento de ingestão com Python e Airflow."

## 5. Estrutura do bullet

A fórmula está em `bullet.formula`; tamanho e número de tecnologias, em `bullet.chars` e `bullet.techs`. O bullet abre com verbo no passado (`verbos_abertura_aceitos`), nunca com fórmula vaga (`aberturas_vagas`), sem termo de `termos_vagos` e sem repetir a abertura de outro bullet da mesma entrada. O escopo é geral: o bullet continua verdadeiro em outras vagas do mesmo eixo, sem nome de empresa da vaga e sem frase copiada do anúncio.

- Bom [bullet] (fictício): "Automatizei a publicação de imagens de contêiner de um serviço de exemplo com Docker e GitHub Actions."
- Ruim [bullet] (fictício): "Responsável por diversas tarefas de infraestrutura, etc."

## 6. Senioridade

Os blocos definem o nível. Os verbos e expressões de `senioridade_inflada` só valem quando o bloco de origem já os usa; sem base, o V21 recusa e a rubrica penaliza o bullet.

- Bom [bullet] (fictício): "Projetei o esquema de dados de um sistema de estoque de exemplo com PostgreSQL."
- Ruim [bullet] (fictício): "Liderei a equipe e arquitetei a plataforma do zero."

## 7. Pontuação (Q5)

Decisão do Filipe: mantém a pontuação do currículo base, e o travessão nunca aparece, em nenhuma forma. O terminador, o separador e os caracteres proibidos estão em `pontuacao`. O V20 (estilo de pontuação) cobre o terminador e o separador; o travessão já é recusado pela checagem de caracteres do F2.3 (`config/validador.yaml`).

- Bom [pontuacao] (fictício): "Modelei o domínio de pedidos; implementei as regras de cobrança com Python."
- Ruim [pontuacao] (fictício): "Modelei o domínio de pedidos — implementei as regras de cobrança com Python"

## 8. Sobre, seções e ordem

O Sobre é reescrito sempre: quem é, o que já construiu e o foco de atuação, em três ou quatro linhas, o que corresponde ao tamanho de `sobre.chars`. Cita ao menos `sobre.techs_minimo` tecnologias do inventário e nenhuma frase de `sobre.frases_vazias`. O foco muda com a família (`foco_sobre`). A ordem das seções está em `ordem_secoes`, as seções que não existem em `secoes_proibidas`, e "Mais projetos" é sempre o último item.

- Bom [sobre] (fictício, família backend): "Desenvolvedor backend focado em APIs e dados relacionais, com experiência em serviços de gestão de estoque para empresas de exemplo, usando Python e PostgreSQL em ambientes conteinerizados. Já construiu APIs REST com testes automatizados e contratos documentados, e busca vagas de backend em que o desenho de dados e a clareza dos serviços sejam parte do trabalho."
- Ruim [sobre] (fictício, família backend): "Profissional proativo e dinâmico, apaixonado por tecnologia, em busca de novos desafios."

## 9. Rubrica de qualidade

Pesos em `rubrica.criterios` (somam 1; nota mínima em `rubrica.nota_minima`). Cada critério vai de 0 a 1 e o total é a soma ponderada. A rubrica só mede; aplicá-la no laço de geração é o F3.3.

| Critério | Mede | Zera quando |
| --- | --- | --- |
| `cobertura_techs` | fração das tecnologias pedidas pela vaga que o inventário sustenta e que o currículo cita | nenhuma delas aparece (se o inventário não sustenta nenhuma, não penaliza) |
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

O prompt tem versão (`prompts/gerar_slots.md`, cabeçalho `versao`); cada tentativa grava a versão e o hash do texto montado. Os blocos e o inventário entram no prompt como fatos do sistema; o texto da vaga entra só dentro da marcação de dado não confiável de `marcacao`, e marcações forjadas dentro da vaga ou dos blocos são trocadas por um texto neutro.
