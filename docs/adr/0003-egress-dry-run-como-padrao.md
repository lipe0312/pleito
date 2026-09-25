# Egress em dry-run como padrao, submit real sob autorizacao explicita

## Status
Aceita

## Contexto
Testar o envio e a unica parte do spike com efeito colateral irreversivel: um formulario
submetido chega numa empresa real. Quatro caminhos foram considerados: candidatura real,
parar antes do submit, sandbox da plataforma, replica local do formulario.

O dry-run prova abrir, achar formulario, anexar PDF e localizar o botao, mas nao prova a
deteccao da pagina de confirmacao nem o email de retorno, que e justamente a parte fragil
do ciclo descrito na secao 18.4 do plano.

## Decisao
`PLEITO_EGRESS_MODO=dry_run` e o padrao e para antes do clique, gravando captura de cada
etapa. Nesse modo o veredito maximo e GO com ressalva, nunca GO pleno, por construcao.

O submit real exige, cumulativamente: modo trocado no `.env`, token de 16+ caracteres, e
uma vaga escolhida pelo Filipe. Uma unica execucao autorizada fecha a prova de confirmacao
e leva o egress a GO.

## Consequencias
- nenhuma empresa recebe candidatura de teste sem decisao consciente
- o veredito global fica em GO com ressalva ate a execucao real acontecer
- `flag_sistema.egress_submit_real` nasce desligada, espelhando o `.env` no banco
