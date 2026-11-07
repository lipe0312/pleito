# Funil de triagem

Do que o coletor gravou até a nota final, gastando o mínimo de token. Código em `src/triagem/`,
ponto de entrada `executar_funil` (`funil.py`). Plano: seções 4.2, 4.3, 6 e 12. Nenhuma etapa antes
da pontuação final usa modelo.

## Ordem

1. **Pendentes e vistas.** Pendente é vaga com `estado = descoberta` e `motivo_descarte` vazio. Vista
   é qualquer outra. Vaga vista nunca é reavaliada.
2. **Duplicata.** Chave por hash de empresa, título e local normalizados (sem acento, caixa ou
   pontuação) ou por URL canônica (sem `www`, fragmento, barra final e parâmetros de rastreio; o id
   da vaga na query fica). Vale contra as vistas e contra o próprio lote. A mesma vaga em duas
   fontes cai aqui. Empresa vazia não gera hash, só a URL.
3. **Filtros eliminatórios**, nesta ordem: função (ADR 0009), senioridade, termo no título, anos
   exigidos, modelo, país, presencial ou híbrido fora da região, idade.
4. **Pré-nota 0 a 100**, sem IA: cobertura das techs que a vaga cita pelo inventário (equivalência
   honesta vale metade), senioridade, modelo, país, empresa alvo e recência, com os pesos de
   `filtros.yaml`. Abaixo de `pre_nota_minima_para_forte`, a vaga é descartada com a nota gravada.
5. **Fila diária.** As que passaram ficam `triada` com a pré-nota em `vaga.nota`. Vão ao modelo as
   `vagas_pre_pontuadas_max` de maior pré-nota. O resto continua `triada` e entra na disputa na
   rodada seguinte.
6. **Pontuação final** (tier forte, tarefa `pontuacao_final`): prompt de `prompts/pontuar_vaga.md`,
   texto da vaga limpo (HTML, caracteres invisíveis), cortado em `descricao_max_chars` e entre as
   marcações de texto não confiável. Resposta em JSON estrito do plano 4.3. Vaga `pontuada` guarda a
   nota final em `vaga.nota`; o resultado inteiro vai para `auditoria` (`acao = pontuacao_final`).
7. **Cache por hash.** A chave é o SHA-256 do prompt montado (modelo, inventário, título e descrição
   cortada). Acerto no cache lê `auditoria` e não chama o roteador.

Dia sem vaga que chegue a `pre_nota_minima_para_forte`: nenhuma chamada ao roteador, nenhuma linha
nova em `uso_llm`.

## Quando o modelo não responde

| Situação | O que acontece |
| --- | --- |
| modelo desabilitado, orçamento esgotado ou erro de rede | a rodada para; o resto fica `triada`, sem descarte |
| flag `sistema_ativo` desligada | `SistemaDesativado` sobe depois de gravar a parte sem modelo |
| resposta fora do schema, família fora da lista, tech fora do inventário | vaga descartada com `pontuacao_invalida` e nunca reavaliada |
| erro do provedor (corpo quebrado, recusa, resposta sem tokens) | a vaga continua `triada` e entra na rodada seguinte; a rodada segue para a próxima |
| `TransicaoRecusada` (o estado da vaga mudou por fora) | registrada em `transicoes_recusadas`; só aquela vaga é pulada |

## Onde cada limite mora

| Limite | Arquivo | Chave |
| --- | --- | --- |
| máximo de vagas ao modelo por rodada | `config/limites.yaml` | `diarios.vagas_pre_pontuadas_max` |
| pré-nota mínima para o forte | `config/limites.yaml` | `llm.pre_nota_minima_para_forte` |
| corte da descrição | `config/limites.yaml` | `llm.descricao_max_chars` |
| orçamento, tier e preço | `config/limites.yaml`, `config/modelos.yaml` | `llm.*`, `tiers.forte` |
| senioridade, país, modelo aceitos | `config/filtros.yaml` | `senioridades_recusadas`, `paises_aceitos`, `modelos_aceitos` |
| anos, título, região, idade, funções aceitas | `config/filtros.yaml` | `eliminatorios.*` |
| pesos da pré-nota | `config/filtros.yaml` | `pontuacao.peso_*` |
| frações da pré-nota e techs fora do inventário | `config/triagem.yaml` | `pre_nota.*` |
| rastreio da URL | `config/triagem.yaml` | `normalizacao.*` |
| tarefa, tier, prompt, tamanhos do JSON, alertas, padrões de injeção | `config/triagem.yaml` | `pontuacao_final.*` |
| vocabulário de função e anos | `config/triagem.yaml` | `termos_*`, `limites` (ADR 0015) |
| famílias e idiomas aceitos na resposta | `config/padroes_curriculo.yaml` | `foco_sobre`, `idiomas` |
| marcação de texto não confiável | `config/padroes_curriculo.yaml` | `marcacao` |

## Motivos de descarte

Texto em `vaga.motivo_descarte`: `codigo` ou `codigo: detalhe`. Códigos: `duplicata`,
`funcao_fora_do_escopo`, `senioridade_recusada`, `titulo_recusado`, `anos_acima_do_maximo`,
`modelo_recusado`, `pais_fora_do_escopo`, `presencial_fora_da_regiao`,
`vaga_antiga`, `pre_nota_abaixo_do_minimo`, `pontuacao_invalida`.

Consulta:

```sql
SELECT split_part(motivo_descarte, ': ', 1) AS motivo, count(*)
FROM pleito.vaga WHERE motivo_descarte IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;
```

Em código: `listar_descartes` e `contar_descartes_por_motivo` em `src/triagem/repositorio.py`.

## Custo conhecido e item futuro

`SQL_VISTAS` lê todas as vagas já vistas a cada rodada, e `SQL_CACHE` varre `auditoria` por
`depois ->> 'hash_entrada'`. Nenhum dos dois tem índice. Com milhares de vagas e poucas rodadas por
dia o custo é desprezível; quando pesar, o item é um índice em `auditoria` sobre esse campo e uma
janela de datas nas vistas. Exige migration, por isso ficou fora da F4.2.

## Segurança

Texto de vaga é dado. O prompt delimita o texto, troca marcações falsas, não habilita ferramenta e
não leva empresa, local nem URL. A resposta só vale se a família, o idioma e os alertas estiverem
nas listas do config, as techs estiverem no inventário e as equivalências na tabela do inventário.
Padrão típico de injeção no texto soma o alerta `texto_suspeito`. É só um alerta: a nota e a
família não mudam e a vaga não é barrada. Quem lê o alerta é a aprovação no painel (F4.9). Os
padrões são compilados ao carregar o config; padrão inválido impede a rodada de começar.
Egress não existe nesta etapa.

## Para a F2.4

O prompt e o schema da pontuação final são `prompts/pontuar_vaga.md` e `esquema_da_pontuacao` em
`src/triagem/pontuacao.py`; `montar_prompt_de_pontuacao` em `src/triagem/prompt.py` monta o texto
de uma vaga. O conjunto de avaliação deve citá-los sem copiar.
