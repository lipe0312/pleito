# Alertas de vaga por email

O LinkedIn manda pelo mesmo domínio alerta de vaga, recomendação, aviso de candidatura vista,
convite, mensagem de recrutador, post, newsletter, Premium e aviso de segurança. Só o alerta com
cartão completo entra no funil de vagas. Tudo o mais é contado e nunca vira vaga (F4.3, issue #25).

Decisão do Filipe: email ambíguo nunca vira vaga e só entra na contagem. Não existe vaga de baixa
confiança.

Gupy e Solides entram pelo mesmo gatilho (F4.5, issue #69). A Solides monta a página no cliente, então
o email é o único caminho para ela; a coleta direta da Gupy é o F4.7. Cada plataforma é uma entrada em
`config/alertas.yaml`; confirmação de candidatura, teste técnico, convite de entrevista, pesquisa e
marketing da mesma plataforma nunca geram vaga. A confirmação continua indo para o F1.2 (`retorno`) e
só atualiza a vaga existente.

## Como rodar

- `make coletar-alertas` (ou `ARGS=--forcar`) lê o Gmail, grava as vagas e imprime a contagem por tipo.
- Cursor próprio em `dados/estado/alertas_cursor.json`, independente do cursor do organizador.
- Intervalo e agendamento em `config/limites.yaml` (`alertas_intervalo_min`, rotina `alertas_coletar`).
- O código só chama `listar`, `historico`, `perfil` e `ler`. Não rotula, não arquiva, não exclui. O
  organizador (`make gmail-organizar`) também não toca em alerta; ele só rotula retorno de candidatura
  e golpe.
- Nenhum acesso ao `linkedin.com`: o link do email nunca é aberto. A URL da vaga é montada pelo
  `link_canonico` do config a partir do id, sem `/comm/` nem parâmetros de rastreio. Teste de
  arquitetura em `tests/test_alertas_arquitetura.py`.

## Plataformas cobertas

| Plataforma | Caixa de alerta | Formato do cartão | Fonte gravada |
|---|---|---|---|
| `linkedin` | `jobs-noreply`, `jobalerts-noreply`, `jobs-listings`, `jobs-noreply-comm` | `trio_antes_do_link` | `linkedin_alertas` |
| `gupy` | `no-reply` | `trio_antes_do_link` | `gupy` |
| `solides` | `system` | `bloco_rotulado` | `solides` |

O domínio exato e a lista de caixas vêm do F1.2 (`config/emails.yaml`). Gupy e Solides gravam na fonte
`gupy` e `solides` que já existem no banco (sem migration). A deduplicação com a coleta direta da Gupy
fica para o F4.7.

InHire, Indeed, Glassdoor, Catho, Vagas.com e InfoJobs ficam fora até haver amostra real: email de
plataforma que não está em `config/alertas.yaml` é ignorado sem registro.

As caixas, os assuntos e os formatos da Gupy e da Solides foram desenhados com fixtures fictícias.
Antes de confiar neles, calibrar com amostra real anonimizada em `dados/` (depende do M1).

## Gatilho em ordem fixa

A primeira regra que decide vence. Cada lista vem de `config/alertas.yaml` (por plataforma), exceto
a regra 1 e a regra 3, que reaproveitam o F1.2 (`config/emails.yaml`).

| # | Regra | Tipo | Exemplo fictício |
|---|---|---|---|
| 1 | remetente de domínio não exato, sem `dmarc=pass`, ou forjado (nome de exibição, reply-to, domínio parecido) | `suspeito` | `jobs-noreply@linkedin.com.golpe.net`, ou `dmarc=fail`, ou sem cabeçalho de autenticação |
| 2 | caixa em `caixas_nunca_vaga` | `mensagem_recrutador` se a caixa está em `caixas_mensagem_recrutador`, senão `outro` | `messages-noreply@`: "Recrutadora Ficticia enviou uma mensagem" com link `/jobs/view/`; `invitations@`: convite; `updates-noreply@`: post; `security-noreply@`: aviso de login |
| 3 | padrão de etapa do F1.2 no assunto ou corpo | `retorno` | `jobs-noreply@`: "Convite para entrevista na Empresa Ficticia" |
| 4 | assunto em `assunto_nunca_vaga` | `outro` | `jobs-noreply@`: "Sua candidatura foi vista por Empresa Ficticia", "Experimente o Premium" |
| 5 | caixa em `caixas_alerta` com pelo menos um cartão completo | `alerta_vaga` | `jobs-noreply@`: "3 novas vagas para estagio em dados" |
| 6 | caixa em `caixas_alerta` sem cartão completo | `alerta_vazio` | `jobalerts-noreply@`: "Nenhuma vaga nova para o seu alerta" |
| 7 | o resto | `outro` | `qualquer@linkedin.com` com dmarc pass e caixa fora das listas |

Observações:

- A regra 1 é o único lugar que olha o domínio e o `Authentication-Results`. Texto do corpo ou do
  assunto, mesmo escrito `dmarc=pass`, nunca conta.
- A regra 2 vem antes da etapa: mensagem de recrutador que cita entrevista continua
  `mensagem_recrutador`.
- `assunto_alerta` não decide nada no LinkedIn. Na Gupy e na Solides (`exige_assunto_alerta: true`) a
  regra 5 e a 6 só valem com assunto de alerta; sem ele o email cai na regra 7 (`outro`), para que um
  aviso de processo com vaga sugerida no fim nunca vire vaga. Em todas é gravado em cada email lido (`assunto_de_alerta`) para calibrar
  a lista sem ler o email.
- Risco conhecido: a regra 3 usa os padrões do F1.2. Um alerta cujo texto contenha, por exemplo,
  "outros candidatos" vira `retorno` e não gera vaga. A coluna `regra` do registro mostra isso.

## Cartão

O cartão é o trio de linhas imediatamente antes de uma linha com o rótulo da vaga
(`rotulos_link`) e o link no padrão `link_vaga`, na ordem de `cartao_campos` (título, empresa,
local). Os campos de `cartao_minimo` precisam estar preenchidos. Linha vazia, separador (`---`) ou
link no lugar do campo conta como campo ausente.

Cartão incompleto é descartado com motivo: `titulo_ausente`, `empresa_ausente`, `local_ausente` ou
`titulo_ruido`. O mesmo id de vaga no mesmo email vale uma vez. A vaga carrega só título, empresa,
local e a URL canônica; a descrição completa é da F4.8.

## Extrator por formato

`src/coletor/alertas/` tem um extrator por formato de email, escolhido pela chave `formato` da
plataforma. Todos devolvem cartões completos, e `extrair_vagas` os transforma em `VagaBruta` com a URL
canônica, sem descrição.

| Formato | Como acha o cartão | Usado por |
|---|---|---|
| `trio_antes_do_link` | as três linhas imediatamente antes da linha do link, na ordem de `cartao_campos` | LinkedIn, Gupy |
| `bloco_rotulado` | linhas `Rótulo: valor` (`rotulos_campos`) desde o último separador ou link, fechadas pela linha do link | Solides |

No `trio_antes_do_link` o cartão só usa as linhas depois do link anterior; se sobram menos linhas que
campos, os campos entram na ordem e o que falta vira descarte. Um id só conta como visto quando um
cartão completo é aceito, então um link incompleto antes do cartão completo não perde a vaga.

Nos dois, o campo que falta descarta o cartão com `<campo>_ausente`; o extrator nunca completa campo com
o cartão vizinho nem devolve vaga incompleta. Sem cartão completo o gatilho devolve `alerta_vazio`.

O `link_vaga` precisa de um grupo nomeado `id` e, se a URL canônica precisa de mais pedaços (a Gupy usa
o subdomínio da empresa), de um grupo nomeado por pedaço. O `link_canonico` só pode citar esses nomes,
então a URL gravada nunca leva rastreio nem texto livre do email.

## Como acrescentar outra plataforma

1. Confirmar que a plataforma existe em `config/emails.yaml` (marcas, domínio exato, caixas).
2. Copiar uma entrada de `config/alertas.yaml`: `fonte` (precisa existir na tabela `fonte`), `formato`,
   `caixas_alerta` (só as já conhecidas do F1.2), `caixas_nunca_vaga`, `assunto_nunca_vaga`,
   `link_vaga` com grupo `id`, `link_canonico`, `rotulos_link`, `cartao_minimo` e limites.
3. Se o email não cabe nos formatos acima, escrever um módulo em `src/coletor/alertas/` com
   `extrair(corpo, plataforma, corpo_max_chars)` e registrá-lo em `EXTRATORES`. O gatilho não muda.
4. Criar `tests/fixtures/alertas_<plataforma>.yaml` com alerta, alerta vazio, confirmação, teste,
   convite, marketing, remetente forjado e injeção no corpo, e rodar os testes de
   `tests/test_alertas_plataformas.py` sobre ela.
5. Acrescentar o domínio na `consulta_inicial` do config, que só vale na primeira leitura.

## O que fica registrado

`dados/estado/alertas_lidos.jsonl` (modo 0600, fora do git), uma linha por email lido de uma
plataforma de alertas:

`id_mensagem`, `plataforma`, `tipo`, `regra`, `assunto_de_alerta`, `cartoes_completos`,
`cartoes_descartados`, `motivos_descarte`, `recebido_em`, `lido_em`.

Sem remetente, assunto nem corpo. O `id_mensagem` já registrado nunca é lido de novo, e a vaga
também é deduplicada por conteúdo ao gravar, então ler o mesmo email duas vezes não duplica vaga.
`contagem_por_tipo(caminho, desde)` devolve a contagem por tipo para o resumo diário (a ligação ao
resumo é o item que cuida do email de resumo).

Email do Gmail que não cita a plataforma (pessoal, outras empresas) é ignorado sem registro.

## Fixtures e testes

`tests/fixtures/alertas_gupy.yaml` e `tests/fixtures/alertas_solides.yaml` têm o mesmo roteiro, todos
fictícios: alerta com 2 vagas, alerta vazio, confirmação de candidatura, teste técnico, convite de
entrevista, marketing e pesquisa com vaga em destaque, caixa de marketing, remetente `.golpe.io`,
`dmarc=fail`, nome de exibição forjado, injeção no corpo e cartão incompleto. Os testes estão em
`tests/test_alertas_plataformas.py`; cada regra tem um teste que falha sem ela.

`tests/fixtures/alertas_linkedin.yaml` tem um caso por tipo, todos fictícios: alerta com 3 vagas,
recomendação, alerta sem vaga, candidatura vista, retorno, convite, mensagem de recrutador com
link, post, newsletter, aviso de login, Premium, remetente `.golpe.net`, `dmarc=fail`, sem
autenticação, nome de exibição forjado, injeção no corpo e no assunto, cartão sem empresa.

Para calibrar com email real, amostras anonimizadas ficam só em `dados/`.
