# Spike de viabilidade antes de qualquer fase do roteiro

## Status
Aceita

## Contexto
O roteiro do plano (secao 14) comeca pela fundacao e chega na primeira aplicacao real na
fase 6. Isso coloca as duas unicas partes nao controladas pela maquina local (trazer vagas
e enviar candidatura) no fim do caminho, depois de seis fases construidas sobre uma premissa
nao testada. Se a Gupy proibir uso automatizado ou exigir CAPTCHA, as fases 4 e 6 morrem.

## Decisao
Um modulo `viabilidade/` dentro do repositorio, isolado de `src/`, ataca primeiro as duas
fronteiras externas e emite GO / GO com ressalva / NO-GO por fonte e por plataforma. O
roteiro so comeca depois do veredito. A flag `sistema_ativo` nasce desligada.

O modulo tambem carrega a extracao e validacao do baseline LaTeX, porque o egress precisa de
um PDF real para anexar: o baseline e insumo do teste de envio, nao uma etapa separada.

## Consequencias
- o custo de um NO-GO cai de seis fases para alguns dias
- `viabilidade/` e descartavel: o que der GO migra para `src/coletor/` e `src/aplicador/`
- a stack do spike e a mesma do plano (httpx, Playwright), para nada ser jogado fora
- atrasa a fundacao em alguns dias
