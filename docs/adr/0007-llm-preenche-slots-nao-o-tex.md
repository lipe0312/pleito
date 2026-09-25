# LLM preenche slots, nunca escreve o .tex inteiro

## Status
Aceita

## Contexto
Q8 do plano. Duas opcoes: a LLM devolve o documento completo e o validador compara com o
base, ou o template Jinja2 trava preambulo e cabecalho e a LLM preenche espacos controlados.

O guia atual pede o documento inteiro num bloco de codigo, o que faz sentido no chat manual
mas nao no pipeline.

## Decisao
Slots. O template trava preambulo, cabecalho, contato, empresas e datas. A LLM devolve JSON
validado contra schema estrito, com IDs que precisam existir em `conteudo/blocos.yaml`, e
todo texto livre passa por escape de LaTeX antes de entrar no template.

## Consequencias
- LaTeX malicioso deixa de ser um vetor pratico: a LLM nao alcanca o preambulo
- gasta menos token por vaga e mantem o padrao visual sem esforco
- o guia precisa ser ajustado (secao 8) para descrever a saida em JSON de slots
- adicionar um campo novo ao curriculo passa a exigir mudanca de template
