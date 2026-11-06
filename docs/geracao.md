# Geração do currículo: slots, com e sem IA

Como `src/gerador/` transforma blocos, inventário e uma vaga em um `.tex` que o validador aceita. A IA nunca escreve o `.tex` (ADR 0007): ela devolve um JSON de slots, o código confere cada id contra os blocos, escapa todo texto livre e preenche o template travado (F2.2). Sem IA, a mesma validação e o mesmo escape rodam sobre uma seleção determinística. Os limites vivem em `config/gerador.yaml`, nada fixo no código.

Entrada única: `gerar_curriculo(familia, idioma, vaga, blocos, inventario, travado, roteador)` em `src/gerador/gerar.py`. Para o modo sem IA direto, `gerar_sem_ia`. Os dois devolvem um `ResultadoGeracao` (`tex`, `slots`, `enfase`, `modo`, `motivo`, versão e hash do prompt) e só devolvem depois de `validar_fonte` aprovar.

## Contrato dos slots

O esquema pydantic é montado em `src/gerador/esquema.py` a partir de `config/gerador.yaml`, em modo estrito: campo extra ou faltando recusa, tipo errado não é convertido, e o JSON schema enviado ao roteador declara `additionalProperties: false` em todo objeto.

| Slot | Forma | Limites (chave do yaml) |
| --- | --- | --- |
| `sobre` | `{texto, techs}` | `slots.sobre.max_chars`, `ia.techs_max`, `ia.tech_max_chars` |
| `disciplinas` | lista de texto | `slots.disciplinas.max_itens` e `max_chars` |
| `experiencias` | lista de `{bloco, bullets: [{id, texto, techs}]}` | `slots.experiencias.max_entradas`, `max_bullets`, `max_chars`, `ia.bullets_min` |
| `projetos` | lista de `{bloco, enfase, bullets: [{id, texto, techs}]}` | `slots.projetos.*`, `ia.entradas_min.projeto` (3 a 4 projetos), `ia.enfase_max` |

`slots.sobre.tipo_bloco` diz de qual bloco vem o Sobre e `slots.disciplinas.tipo_ancora` diz de qual âncora do inventário vêm as disciplinas aceitas.

`techs` são as tecnologias que levam `\tech{}` dentro do texto; `enfase` são as tecnologias que o projeto destaca nesta versão. O `\tech` é montado pelo código, nunca vem no texto da IA.

## O que descarta a resposta

Qualquer um destes vira `RespostaDescartada` e nada chega ao template:

- JSON inválido, campo extra ou faltando, tipo errado, lista ou texto acima do limite do yaml
- id de bloco inexistente ou de outro tipo, bloco repetido, id de bullet que não é do bloco, bullet repetido
- experiência omitida ou fora da ordem dos blocos (`ia.tipos_na_ordem_dos_blocos`: a IA ordena os bullets, não as experiências)
- tecnologia fora do inventário em `techs`, ou `enfase` fora das tecnologias do próprio bloco
- disciplina que não é âncora `disciplina` do inventário

O roteador já grava `invalida` em `uso_llm` quando o JSON ou o schema falham. Nova tentativa, corte de página e correção pela IA são do F3.3; aqui a função só levanta o erro.

## Caminho com IA

1. `montar_prompt` (F3.0) com o modelo versionado de `prompts/gerar_slots.md`: regras de `config/padroes_curriculo.yaml`, blocos e inventário do idioma, e a vaga entre as marcas de dado não confiável. Telefone e email nunca entram: o cabeçalho é travado no template e não passa pelo prompt.
2. `roteador.chamar(ia.tarefa, ia.tier, ...)`: tier forte, reserva de orçamento antes do envio, saída estruturada estrita, sem ferramenta. A versão gravada em `uso_llm.prompt_versao` leva a versão do modelo e os 12 primeiros caracteres do hash do texto.
3. Conferência dos ids e dos limites (`src/gerador/resposta.py`) e renderização (`escapar_latex`, `compor_texto`).
4. `exigir_fonte_valida`: se o validador recusar, levanta `CurriculoInvalido` e o `.tex` não é devolvido. Esse erro não vira `RespostaDescartada`: ele carrega a lista de violações (`erro.resultado`), que o F3.3 devolve à IA na nova tentativa. O caminho sem IA levanta o mesmo erro.

`sistema_ativo` desligado levanta `SistemaDesativado` e nada cai para o modo sem IA. Falha de rede propaga para quem decide a tentativa.

## Caminho sem IA

Roda quando o tier está desligado ou não avaliado (`ModeloIndisponivel`, motivo `modelo_indisponivel`), quando o orçamento acabou (`OrcamentoEsgotado`, motivo `sem_orcamento`) ou quando não há roteador (`sem_roteador`). Nenhum desses casos reserva nem grava `uso_llm`, e os testes provam isso com a lista de reservas vazia.

A regra (`src/gerador/selecao.py`) é determinística e usa só a família, as tecnologias do inventário que aparecem no texto da vaga e `sem_ia` do yaml:

- Sobre: a redação aprovada do bloco `sobre`, sem mudança
- cada bullet pontua `peso_familia` se a família está nas `familias` do bullet, mais `peso_tech` por tecnologia do bullet que a vaga cita
- experiências: todas, na ordem dos blocos, com os `bullets_por_tipo.experiencia` melhores bullets cada uma
- projetos: os `entradas_por_tipo.projeto` de maior pontuação, com os `bullets_por_tipo.projeto` melhores de cada; se houver menos blocos do que o pedido, usa os que existem
- empate sempre resolvido pela ordem dos blocos, então a mesma entrada gera o mesmo `.tex`
- disciplinas: as âncoras `disciplina` do inventário, as das tecnologias da vaga primeiro
- bullet sem `familias` pontua só pela vaga e continua elegível em toda família

O texto da vaga só serve para achar tecnologias do inventário e nunca entra no `.tex`.

## Segurança do `.tex`

- todo texto livre passa por `escapar_latex` e o Jinja só imprime `LatexSeguro` (F2.2)
- o único comando que a IA influencia é `\tech{}`, com nome do inventário
- a saída passa por `validar_fonte` antes de ser devolvida; quem a compila (`compilar`) recebe o `.tex` já aprovado
- a compilação roda sem shell escape e `compilar` recusa PDF acima de `compilacao.paginas_max` (F2.2); isso fica fora de `gerar_curriculo`, que só entrega a fonte aprovada

## Como conferir

```bash
.venv/bin/python -m pytest tests/test_gerador_esquema.py tests/test_gerador_sem_ia.py tests/test_gerador_ia.py -q
.venv/bin/python -m pytest -m latex tests/test_gerador_geracao_latex.py -q
```

Os testes usam um cliente falso no transporte do roteador e blocos fictícios; nenhuma chamada real.
