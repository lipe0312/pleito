# Padrões de tela do painel

Fonte das decisões visuais do painel local (`src/painel/`). Tela nova reaproveita estes blocos;
bloco novo entra aqui no mesmo PR.

## Montagem

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

## Blocos

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

## Preview

`make painel-ficticio` sobe o painel em 127.0.0.1 com `tests/fixtures/painel_ficticio.yaml`, sem
banco. A fixture traz texto de ataque (`<script>`, `<img onerror>`) para conferir o escape.
