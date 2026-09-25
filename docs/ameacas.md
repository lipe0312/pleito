# Modelo de ameacas

Consolida a secao 10 do plano e amarra cada ameaca ao ponto do codigo que a contem.

## Superficie

| Entrada | Natureza | Confianca |
| --- | --- | --- |
| texto de vaga (API ou HTML) | atacante controla | nenhuma |
| corpo de email de retorno | atacante controla | nenhuma |
| formulario de plataforma | terceiro, muda sem aviso | nenhuma |
| guia de adaptacao e blocos | Filipe escreveu | total |
| config YAML | Filipe escreveu | total |
| saida da LLM | derivada de entrada nao confiavel | nenhuma |

## Ameacas e contencao

| # | Ameaca | Contencao | Onde |
| --- | --- | --- | --- |
| A1 | prompt injection no texto da vaga | texto de vaga nunca entra como instrucao, so como dado; saida obrigatoriamente JSON contra schema; IDs restritos a `blocos.yaml` | `src/llm/`, plano 8.2 |
| A2 | LaTeX malicioso via LLM | template trava preambulo, LLM so preenche slots, escape antes de entrar, lista de comandos proibidos, `-no-shell-escape` | `viabilidade/baseline/validar.py`, ADR 0007 |
| A3 | coleta em dominio nao autorizado | allowlist em `config/fontes.yaml`, `exigir_dominio_permitido` em toda requisicao, rota do navegador aborta o resto | `viabilidade/conformidade.py`, `egress/navegador.py` |
| A4 | violar robots.txt ou termos de uso | `consultar_robots` antes de coletar; `requer_revisao_tos` impede GO pleno sem leitura dos termos | `viabilidade/conformidade.py` |
| A5 | candidatura enviada sem aprovacao | token de aprovacao de uso unico com expiracao, hash do PDF conferido, RLS so permite consumir token valido | `db/policies/0001` |
| A6 | envio para a vaga errada ou versao errada | hash do PDF aprovado igual ao enviado, candidatura unica por vaga | plano 8.3, constraint `candidatura_unica` |
| A7 | curriculo de duas paginas enviado | constraint `versao_uma_pagina` no banco, alem do validador V2 | `db/migrations/0001` |
| A8 | email falso de entrevista muda status | SPF/DKIM/DMARC, dominio coerente, limite de confianca, RLS recusa insert nao autenticado com confianca 1.0 | plano 8.5, `db/policies/0001` |
| A9 | vazamento de segredo pelo git | `.gitignore` cobre `.env`, `dados/`, `segredos/`, perfil do navegador | ADR 0008 |
| A10 | senha de plataforma capturada | sistema nunca le nem digita senha; `exigir_campo_seguro` recusa seletor com password, senha, cpf, cartao | `egress/navegador.py` |
| A11 | CAPTCHA contornado | nunca resolvido; deteccao vira NO-GO ou pendencia | `egress/fluxo.py` |
| A12 | SQL injection | acesso sempre parametrizado, papel de aplicacao sem DDL nem DELETE | `src/db/` |
| A13 | painel exposto na rede | bind em 127.0.0.1, banco e pgAdmin idem | `docker-compose.yml` |
| A14 | auditoria apagada para esconder acao | `auditoria` aceita apenas INSERT para os papeis de aplicacao | `db/policies/0001` |
| A15 | custo de LLM fugindo do controle | orcamento diario com corte, tiering, registro em `uso_llm` | `config/limites.yaml` |

## Fora de escopo por decisao

- automatizar LinkedIn, em qualquer forma
- resolver CAPTCHA, criar conta, recuperar senha
- responder teste tecnico ou questionario comportamental
- preencher dado sensivel de diversidade sem confirmacao explicita (plano 18.3)
