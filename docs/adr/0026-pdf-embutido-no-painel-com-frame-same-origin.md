# PDF embutido no painel com frame same-origin e CSP ajustada só para isso

## Status
Aceita. Estende a ADR 0023.

## Contexto
O visualizador de currículos (F3.4) precisa mostrar o PDF gerado dentro da tela do currículo. A
CSP da ADR 0023 (`default-src 'none'`) e os cabeçalhos `X-Frame-Options: DENY` e
`frame-ancestors 'none'` impedem qualquer frame, inclusive o do próprio painel. A alternativa
sem frame, converter o PDF em PNG com `pdftoppm`, adiciona uma ferramenta externa ao caminho da
tela e perde seleção de texto e zoom. Decisão do Filipe: PDF embutido, sem dependência nova.

## Decisão
- Páginas do painel: a CSP ganha só `frame-src 'self'` (em `config/painel.yaml`, bloco `csp`).
  Nenhuma outra diretiva muda: `default-src 'none'`, `script-src 'self'`, `connect-src 'self'`,
  `frame-ancestors 'none'` e `X-Frame-Options: DENY` continuam em todas as páginas e nos estáticos.
- Rota do PDF (`/pdf/<tipo>/<id>`, prefixo em `pdf.prefixo_rota`): só ela troca `frame-ancestors`
  para `'self'` e `X-Frame-Options` para `SAMEORIGIN`, pelo bloco `pdf` do mesmo arquivo. Outra
  origem continua sem poder embutir o painel nem o PDF.
- O middleware (`src/painel/seguranca.py`) escolhe o conjunto de cabeçalhos pelo prefixo do
  caminho; resposta 404 da rota do PDF recebe os mesmos cabeçalhos, nenhuma outra rota recebe.
- `object-src` e `embed` não entram: o PDF vai num `<iframe>`.
- O PDF é lido de `dados/` por um id que precisa estar na listagem (nome que casa
  `curriculos.padrao_id`, pasta que não é link simbólico, arquivo até `pdf_max_bytes`). O id da
  URL nunca vira caminho; `../` e variações só dão 404. Servido com `application/pdf` e
  `X-Content-Type-Options: nosniff`.
- O `htmx-config` passa a vir de `config/painel.yaml` (`htmx`) e ganha `responseHandling` para o
  HTMX trocar o item também nas respostas 404, 409 e 422 do formulário de aprovação; as demais
  respostas de erro (inclusive o 403 do CSRF) continuam sem troca.

## Consequências
- um PDF same-origin renderiza no visualizador do navegador, sem biblioteca JS e sem CDN
- headless Chromium não mostra o visualizador de PDF; a conferência visual é no navegador de
  verdade (Chrome ou Safari) com `make painel-ficticio`
- se algum navegador recusar o PDF por causa de `default-src 'none'` na resposta do PDF, o ajuste
  é no bloco `pdf.csp` e volta a esta ADR
- alternativa descartada: afrouxar `frame-ancestors` e `X-Frame-Options` no painel inteiro, que
  deixaria toda tela embutível por si mesma sem necessidade
- alternativa descartada: PNG por `pdftoppm`, por dependência de sistema e perda de texto
