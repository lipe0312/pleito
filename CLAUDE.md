# pleito

Spike de viabilidade antes de qualquer fase do roteiro. Ler `README.md`, `docs/PLANO.md` e
`docs/adr/` antes de mudar arquitetura.

## Constraints de codigo

- **sem comentario e sem docstring.** O nome diz o que faz. Explicacao vai em `docs/`, ADR ou
  nome de teste. Codigo que precisa de comentario para ser entendido precisa ser reescrito.
- portugues sem acento em identificador, tabela e coluna; acento so em texto de `docs/`
- nada de valor fixo no codigo: fonte, board, termo de busca, limite e horario vem de `config/`
- `rtk` sempre, para toda operacao de git, build e inspecao de arquivo. Excecao: quando a
  saida alimentar outro comando num pipeline, use o binario (`/usr/bin/grep`, `awk`), porque a
  funcao de shell do rtk resume a saida e quebra o pipe
- teste antes da implementacao quando o comportamento for uma regra, nao um detalhe

## Constraints de commit

- **nunca assinar commit.** Sem `Co-Authored-By`, sem `Generated with`, sem qualquer linha de
  atribuicao a ferramenta ou modelo. A mensagem termina no conteudo tecnico.
- mensagem no imperativo, primeira linha curta, corpo explicando o porque e o que foi verificado

## Constraints de fluxo

- toda mudanca de regra de seguranca ou de veredito precisa de teste que falha sem ela
- `dados/` e `segredos/` nunca entram em commit, nem com `-f`
- nenhuma credencial, senha ou token em arquivo versionado, incluindo exemplo
- egress em `dry_run` por padrao; submit real e decisao do Filipe, por execucao
- LinkedIn nunca e automatizado

## A definir depois do spike

- worktree obrigatorio por feature, com paralelizacao de features que nao se cruzam
- hook de pre-commit barrando `dados/`, `segredos/` e padrao de segredo
- politica de branch e de revisao
