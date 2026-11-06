# Design do painel

Fonte de verdade visual do painel local (`src/painel/`), do HTML do email de resumo e dos previews de aprovação. Lido pela skill `ui-build`; mudança aqui entra no mesmo PR da tela e é aprovada pelo Filipe.

## Princípios

1. Ferramenta de trabalho de uma pessoa: a tela serve para decidir sobre vagas, não para impressionar.
2. Dado real na tela, em ordem de leitura: empresa, título, fonte, nota, motivo da nota, etapa.
3. Texto externo (vaga, email, saída de LLM) é sempre texto, nunca HTML.
4. Nada sai da máquina: sem CDN, sem fonte remota, sem imagem remota. HTMX local, CSS local.
5. Ação irreversível nunca é a padrão e sempre diz o efeito antes de confirmar.

## Tokens

| Token | Claro | Escuro | Uso |
| --- | --- | --- | --- |
| `--tinta` | `#1c1f23` | `#e8eaed` | texto principal |
| `--fundo` | `#f7f7f5` | `#16181b` | fundo da página |
| `--superficie` | `#ffffff` | `#1f2226` | linha, cartão, tabela |
| `--borda` | `#d7dbe0` | `#33373d` | divisória |
| `--apoio` | `#5b636e` | `#9aa1ab` | texto secundário, rótulo |
| `--marca` | `#2f6f4f` | `#6fcf97` | ação primária, foco |
| `--ok` | `#047857` | `#34d399` | aprovada, autenticado |
| `--atencao` | `#b45309` | `#fbbf24` | classificar, orçamento perto do teto |
| `--erro` | `#b91c1c` | `#f87171` | falha, recusa do validador |
| `--suspeito` | `#7c3aed` | `#c4b5fd` | email suspeito, vaga com sinal de golpe |

Tipografia: pilha do sistema (`system-ui, -apple-system, "Segoe UI", sans-serif`), corpo 15 px, tabela 14 px, título 22 px. Números com `font-variant-numeric: tabular-nums`. Código e hash em `ui-monospace, Menlo, monospace`.

Espaço em múltiplos de 4 px. Raio 8 px em cartão, 6 px em botão. Sem sombra além de `0 1px 0 var(--borda)`.

## Componentes

| Componente | Regra |
| --- | --- |
| Linha de vaga | uma linha por vaga; nota à direita em número tabular; motivo em texto de apoio embaixo |
| Selo de etapa | texto + cor semântica, nunca só cor |
| Diff de currículo | lado a lado em 1280, empilhado em 390; entrou e saiu marcados também por símbolo (+ e −) |
| Ação primária | botão `--marca` cheio, uma por tela ou por linha |
| Ação irreversível | botão contornado em `--erro`, confirmação em HTML na própria tela, texto com o efeito |
| Estado vazio | diz o que aconteceu ("Nenhuma vaga acima do corte hoje") e quando roda de novo |
| Erro | diz o que fazer, com o comando quando houver |
| Gasto de LLM | valor do dia e do mês com o teto ao lado, em número tabular |

## Email de resumo

HTML simples, uma coluna, largura máxima 600 px, sem imagem, sem script, sem link que muda estado. Funciona com o HTML desligado (parte texto obrigatória). Assunto com a contagem do dia.

## Anti-padrões

Gradiente, glassmorphism, emoji como ícone, sombra pesada, texto centralizado em tudo, card para tudo, métricas genéricas na tela Hoje, ícone sem texto em ação irreversível, número de exemplo que parece real.


## Montagem (implementado no F1.6)

- HTML em `src/painel/templates/`, um arquivo por bloco. A montagem usa `renderizar`
  (`{{nome}}`), que escapa todo valor; o resultado de `renderizar` é `HtmlSeguro` e entra em outro
  modelo sem novo escape. Texto vindo de fora (vaga, empresa, remetente, detalhe) nunca vira
  `HtmlSeguro` por outro caminho.
- Sem script inline, sem `style=` e sem `on*=` (CSP da ADR 0023). CSS só em
  `src/painel/static/painel.css`; JS só o HTMX local.
- Rótulos, textos de estado vazio, ordem das etapas, formatos de data e fuso vêm de
  `config/painel.yaml`.
- Leitura pelo papel do painel (ADR 0016): `src/painel/repositorio.py`, só `SELECT`, conexão
  `read_only`, tabelas com o schema `pleito.` (o login do painel não tem `search_path`).

## Blocos (implementado no F1.6)

- **Barra superior:** marca e navegação por link; a tela atual leva `aria-current="page"`.
- **Seção:** `h2` com nome e contagem em número tabular.
- **Lista:** `ul.lista` com `li.item`. Linha de 3 colunas (hora, corpo, selos); em 600 px ou
  menos os selos descem para baixo do corpo. Item de alerta, atenção ou erro ganha borda
  esquerda colorida; o estado sempre aparece também em texto no selo.
- **Selo:** `selo--ok|alerta|atencao|erro|neutro`. Cor nunca é o único sinal.
- **Estado vazio:** `p.vazio` dizendo que não há nada e, quando couber, o que fazer.
- **Erro de leitura:** página 503 com título e uma ação (`make banco-status`); nunca mostra a
  mensagem da exceção.
- **Aviso de dados fictícios:** faixa no topo quando o painel roda com `make painel-ficticio`.

## Preview (implementado no F1.6)

`make painel-ficticio` sobe o painel em 127.0.0.1 com `tests/fixtures/painel_ficticio.yaml`, sem
banco. A fixture traz texto de ataque (`<script>`, `<img onerror>`) para conferir o escape.
