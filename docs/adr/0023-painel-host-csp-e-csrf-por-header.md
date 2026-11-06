# Painel protegido por Host, CSP estrita e token CSRF em header

## Status
Aceita

## Contexto
O painel é local (`127.0.0.1`), mas qualquer página aberta no navegador consegue chamar
`localhost` (DNS rebinding, formulário cruzado, `fetch`). O PLANO (seções 5 e 10) pede checagem
de Host, CSP estrita, token CSRF em toda ação e texto externo como texto puro. O ambiente não
tem Jinja2 nem `python-multipart`, e a regra é não acrescentar dependência para isso.

## Decisão
- Um middleware ASGI (`src/painel/seguranca.py`) envolve toda a aplicação, inclusive estáticos,
  404 e as próprias recusas.
- Host: aceita só `hosts_permitidos:porta` de `config/painel.yaml`; qualquer outro, ou Host
  repetido, recebe 400 antes de qualquer outra checagem.
- Método fora de `metodos_seguros`: exige `Origin` do próprio painel (quando enviado),
  `Sec-Fetch-Site` same-origin ou none, e o token no cabeçalho `csrf_cabecalho`. Falha → 403.
- Token: `secrets.token_urlsafe(32)` gerado por processo, só em memória, comparado com
  `secrets.compare_digest`. Não vai em cookie, query nem corpo; a página o entrega ao HTMX por
  `hx-headers` no `<body>`, sem script inline. Reiniciar o painel invalida o token e a aba
  precisa ser recarregada.
- CSP e demais cabeçalhos (`nosniff`, `X-Frame-Options`, `Referrer-Policy`, `no-store`) vêm de
  `config/painel.yaml`. A CSP é `default-src 'none'` com `'self'` só no que precisa. Para o HTMX
  caber nela, a página liga `includeIndicatorStyles: false` e `allowEval: false` em
  `htmx-config`.
- Texto externo passa por `renderizar` (`src/painel/renderizar.py`): `{{nome}}` vira
  `html.escape(..., quote=True)` em uma só passada, sem reinterpretar o valor. Placeholder sem
  valor falha. Em modelo, todo atributo com valor externo usa aspas.

## Consequências
- header em vez de cookie ou campo de formulário: formulário HTML puro não funciona sem
  `hx-post`; toda ação do painel passa pelo HTMX
- sem estilo inline nem `style=`: o CSS das telas vem de arquivo em `/assets`
- alternativa descartada: double-submit com cookie, que abre superfície de cookie sem ganho para
  um painel de um usuário só
- tela nova usa `renderizar` e não monta HTML por concatenação
