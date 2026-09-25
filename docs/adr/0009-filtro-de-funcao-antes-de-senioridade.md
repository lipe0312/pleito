# Filtro de funcao como eliminatorio, antes da senioridade

## Status
Aceita

## Contexto
A secao 6.1 do plano define os filtros eliminatorios em torno de senioridade, modelo de
trabalho e pais. Ao rodar o ingest sobre 2484 vagas reais, 64% ficaram com senioridade
indefinida, o que parecia falha do classificador.

A amostra mostrou outra coisa: Product Manager, Course Writer, Executivo Comercial, Auxiliar
Tecnico de Logistica, Office Assistant, Technicien de maintenance. Nao eram vagas de tecnologia
mal classificadas, eram vagas de outra area. O ruido dominante das fontes e area errada, nao
senioridade errada.

## Decisao
`viabilidade/triagem.py` classifica a funcao em engenharia, dados, infra, qa, outra ou
indefinida, por termo no titulo e, em segunda tentativa, no inicio da descricao. Funcao entra
como eliminatorio antes da senioridade, e passa a compor os campos de completude da triagem.

No mesmo modulo, `extrair_anos_experiencia` le a exigencia de anos declarada na descricao, que
o plano ja previa como eliminatorio mas nao tinha de onde tirar.

Ambos deterministicos, sem LLM, coerentes com o principio de custo minimo.

## Consequencias
- o funil final fica em 303 de 2484 vagas, 12,2%, contra 690 sem o filtro de funcao
- 1090 vagas classificadas como tecnologia e 551 descartadas como area errada
- lista de termos em codigo, nao em YAML: e vocabulario de dominio estavel, mas se virar ponto
  de ajuste frequente deve migrar para `config/`
- 843 vagas seguem com funcao indefinida, tipicamente titulo curto sem termo reconhecivel. Ficam
  fora do funil por precaucao, o que custa recall
