# Fontes de vaga: ATS por empresa, agregadores com API publica e um portal brasileiro

## Status
Aceita

## Contexto
A secao 11 do plano listava alertas de email, Gupy, Solides, InHire e as APIs de Greenhouse,
Lever e Ashby. Faltava saber quais existem, quais respondem e quais entregam volume.

## Decisao
Onze fontes sondadas e testadas com requisicao real, em tres familias:

**ATS por empresa**, que e a vaga anunciada pela propria empresa. Greenhouse com 14 boards
validos, incluindo Stone, XP, C6, QuintoAndar, Gympass, EBANX e VTEX. Ashby com 11. Lever com
apenas 2, o que torna Lever marginal.

**Agregadores com API publica documentada**: Remotive, Arbeitnow, Himalayas, RemoteOK e Jobicy.
Todos remoto, todos respondem sem chave. RemoteOK exige link de volta por termo de uso, e isso
fica registrado em `atribuicao_exigida` na config e na evidencia da coleta.

**Portal brasileiro**: Gupy, pela API do portal de empregabilidade, publica e sem chave. Unica
fonte com volume brasileiro relevante, 1737 vagas para "estagio".

Mais duas escolhas fora do obvio: a thread mensal Ask HN Who is hiring, lida pela API do
Algolia, que rende 211 vagas de texto livre com 91% de completude; e o parser de email de
alerta do LinkedIn, que mantem o LinkedIn como fonte sem nunca automatizar o site.

Solides fica fora: monta a listagem no cliente, sem dado no HTML inicial.

Workable, SmartRecruiters, Personio e Comeet ficam registrados em `descobertas_pendentes`, com
endpoint verificado e identificador de empresa desconhecido.

## Consequencias
- 2484 vagas por rodada com 0,6% de duplicidade entre fontes
- dependencia forte da Gupy para o mercado brasileiro: 269 das 303 vagas do funil final
- toda fonte passa por allowlist de dominio e consulta a robots.txt antes da primeira requisicao
- agregador de remoto tende a vaga internacional senior, o que explica completude alta e
  elegibilidade baixa
