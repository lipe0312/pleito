# Gupy segue sem coleta direta enquanto o veredito dos termos for proibe

## Status
Aceita

## Contexto
O F4.4 (`docs/fontes-termos.md`, 2026-11-07) deu `proibe (ambíguo)` para a Gupy: a URL de termos
serve a página inicial do portal, sem texto sobre uso automatizado, e o robots de
`portal.gupy.io` tem `Disallow:` vazio. Caso ambíguo vale como `proibe` até o Filipe decidir.

A ADR 0011 registra que os termos da Gupy proíbem "agregar, copiar ou duplicar partes" das
vagas. Gravar vagas no banco é cópia. A ADR 0010 previa a Gupy como portal de ingest pela API
pública; o F4.7 existia para isso e dependia do veredito `permite`.

## Decisão
O F4.7 fecha sem código. Não há coletor direto da Gupy, nem bloco em `config/fontes.yaml`, nem
endpoint do portal na allowlist. A leitura de vagas públicas continua permitida pela ADR 0011 só
quando o Filipe a faz; o pleito não a automatiza. Aplicar continua manual (F6.3).

O funil brasileiro passa a depender de:
- alertas de email da Gupy que o próprio Filipe recebe (F4.5, `src/coletor/alertas/`), sem
  acesso ao site
- ATS público das empresas-alvo (F4.8, Greenhouse, Ashby e outros com veredito coletável)

## Condições para reabrir
1. o Filipe lê os termos da Gupy fora do agente e registra em `docs/fontes-termos.md` o trecho
   que decide, com o veredito `permite` ou `permite_com_condicao`
2. nova decisão no backlog reabre o F4.7: coletor com `termos` em `config/fontes.yaml`,
   allowlist só de leitura pública, teste de arquitetura sem candidatura nem login, e
   deduplicação com a mesma vaga vinda por alerta
3. a ADR 0011 continua valendo: login e candidatura nunca são automatizados

## Consequências
- o volume da Gupy no funil fica limitado ao que chega por alerta de email
- nenhuma mudança em código, config, banco ou testes
