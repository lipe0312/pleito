# Gupy fica como pendencia manual, nunca como aplicador automatico

## Status
Aceita

## Contexto
Duas evidencias, testadas separadamente: os termos de uso da Gupy proibem "agregar, copiar ou
duplicar partes" das vagas, e o login de candidato (`/candidates/signin`) tem Cloudflare
Turnstile ativo, confirmado no console do navegador do Filipe tentando logar. Turnstile existe
para detectar navegador controlado por automacao.

Foi cogitado extrair a sessao autenticada de um navegador pessoal (login manual fora da
automacao) e injetar no perfil do Playwright, para contornar o Turnstile no clique de aplicar.

## Decisao
Nao construir esse contorno. E transplante de sessao para disfarcar automacao de humano, contra
um controle anti-bot ativo, sobre uma clausula contratual que ja proibe a acao de fundo. Gupy
fica como fonte de **ingest** (GO com ressalva, API publica, ver ADR 0010), nunca como
plataforma de **egress**. Toda vaga da Gupy vira pendencia no painel: link direto, currículo ja
gerado e validado, o Filipe clica.

Isso nao e desvio do plano. A secao 4.9 e a Q7 ja descrevem formulario nao tratavel virando
pendencia como fluxo normal, nao excecao. O valor central do sistema — a variante do curriculo
sempre pronta e validada — nao depende do envio ser automatico.

## Consequencias
- Greenhouse e Ashby seguem como os unicos candidatos a aplicador automatico verificado
- a fila de pendencias (secao 4.9 do plano) precisa suportar bem esse caso desde a fase 6, nao
  como excecao rara: a maior fonte de volume brasileiro (Gupy) sempre cai nela
- se a Gupy mudar o login ou a Turnstile parar de aparecer no futuro, a decisao pode ser
  revisitada, mas o padrao e nao tentar contornar controle anti-bot ativo
