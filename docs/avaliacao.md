# Conjunto de avaliação dos tiers de IA

Os tiers do `config/modelos.yaml` nascem com `habilitado: false` (ADR 0017). Um tier só é ligado
num PR próprio (manual M8) que cita um relatório **real** com veredito `aprovado` deste runner. O
teste `tests/test_avaliacao_liberacao.py` falha se algum tier tiver `habilitado: true` sem
`avaliacao.status: aprovado`, `conjunto` e `data`.

## Como rodar

```bash
make avaliar TIER=forte              # offline: cliente falso, sem rede, sem banco, sem custo
make avaliar TIER=forte ARGS=--real  # real: OpenAI pelo roteador, gasta orçamento
```

- **Offline** (padrão): o provedor é trocado por um cliente falso que devolve os slots copiados dos
  blocos. Serve para conferir o encanamento; o relatório sai com `modo: offline` e não libera tier.
- **Real** (`--real`): o roteador reserva o custo máximo de cada chamada no banco antes de enviar
  (`uso_llm`, limites de `config/limites.yaml`), exige a flag `sistema_ativo` e a
  `OPENAI_API_KEY` do `.env`. Sem orçamento, sem chave ou com o tier sem caso, a execução vira falha
  e o veredito é `reprovado`; nada cai em fallback silencioso.
- Durante a avaliação, só o tier avaliado é liberado, e só em memória
  (`src/avaliacao/liberacao.py`). O `config/modelos.yaml` não muda.
- Saída: `0` aprovado, `1` reprovado, `2` ambiente impediu a rodada (flag desligada, banco, rede).

## O que entra no conjunto

| Origem | Onde | Versionado |
| --- | --- | --- |
| Armadilhas fictícias | `tests/fixtures/avaliacao/armadilhas/*.yaml` | sim |
| Conteúdo fictício das armadilhas | `tests/fixtures/avaliacao/conteudo/` | sim |
| Vagas reais anonimizadas | `dados/avaliacao/vagas/*.yaml` | nunca |

As armadilhas cobrem os tipos de `conjunto_avaliacao.armadilhas` em `config/modelos.yaml`:
injeção no texto da vaga, tecnologia fora do inventário, vaga sênior disfarçada de júnior e email
falso de entrevista. Cada uma lista `proibidos`: termos que não podem aparecer em nenhum slot.

Vaga real usa o mesmo formato, sem `tipo` e sem `proibidos` (o nome do arquivo vira o id):

```yaml
idioma: pt
familia: backend_arquitetura
empresa: Nome da empresa
titulo: Título da vaga
texto: |
  Texto anonimizado da vaga.
```

Vagas reais rodam contra os blocos de `dados/conteudo/`. Se o conteúdo não existir, elas são
contadas em `vagas_reais.sem_conteudo` e ficam de fora.

## Casos de prompt

`config/avaliacao.yaml`, em `casos`, liga cada prompt a um executor de `src/avaliacao/execucao.py`,
à tarefa do roteador e aos tipos de armadilha que ele consome. Um tier só roda os casos cuja tarefa
está no seu `uso`. Hoje existe `escrita_slots` (gerador do F3.1); o prompt de pontuação do F4.2
entra com uma nova entrada em `casos` e um executor registrado em `EXECUTORES`.

O executor `gerar_e_validar` é provisório: chama o gerador e o validador direto, uma tentativa por
vaga. O laço com retry e corte do F3.3 vai substituí-lo.

## Como uma execução falha

| Falha | Quando |
| --- | --- |
| `esquema` | resposta fora do schema estrito ou com bloco, bullet ou tech que não existe |
| regra do validador (`latex`, `tecnologia`, `senioridade`, ...) | o `.tex` gerado viola a regra |
| `proibido` | algum slot contém um termo de `proibidos` da armadilha |
| `sem_ia_<motivo>` | o modelo não respondeu (indisponível, sem orçamento) e o gerador caiu no modo sem IA |

Armadilha de injeção que muda qualquer slot fora do schema conta como falha do tier. Página e
layout (`regras_fora: [paginas]`) não entram: dependem da compilação e do F2.6.

## Como ler o relatório

O relatório é um JSON em `dados/avaliacao/relatorios/<data>_<tier>_<modo>.json`, fora do git.
Ele não traz o texto das vagas.

| Campo | Significado |
| --- | --- |
| `data`, `tier`, `modo`, `provedor`, `modelo` | quando e o que foi avaliado |
| `versao_conjunto` | `v<versao_conjunto>-<hash>`; o hash muda se qualquer armadilha ou vaga mudar |
| `versoes_prompt` | versão do modelo de prompt por caso (ex.: `gerar_slots_v1`) |
| `taxa_aprovacao` | execuções sem nenhuma falha sobre o total |
| `taxa_por_regra` | para cada regra, a fração de execuções que não falhou nela |
| `falhas_por_armadilha` | quantas armadilhas de cada tipo falharam |
| `armadilhas` | cada armadilha com o caso, se passou e as falhas |
| `armadilhas_sem_cobertura` | tipo exigido que nenhum caso do tier rodou |
| `vagas_reais` | avaliadas, aprovadas, falhas agregadas por regra e as que ficaram sem conteúdo |
| `custo_usd`, `chamadas` | custo calculado pelos tokens de cada resposta (simulado no offline) |
| `veredito`, `motivos` | `aprovado` só sem motivo de reprovação |

O tier é reprovado se nenhum caso rodou, se algum tipo de armadilha ficou sem cobertura, se alguma
armadilha falhou ou se `taxa_aprovacao` ficou abaixo de `taxa_minima_aprovacao`.

## Para ligar um tier (M8)

1. Rodar `make avaliar TIER=<tier> ARGS=--real` com orçamento do dia livre.
2. Conferir `modo: real` e `veredito: aprovado` no relatório.
3. Num PR próprio, preencher `avaliacao.status: aprovado`, `conjunto` (o `versao_conjunto` do
   relatório) e `data`, e só então `habilitado: true`, citando o relatório no PR.

Troca de modelo, de prompt ou de regra de validação repete o processo
(`conjunto_avaliacao.obrigatorio_antes_de_trocar`).
