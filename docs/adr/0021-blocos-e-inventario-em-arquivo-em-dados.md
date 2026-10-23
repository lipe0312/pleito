# Blocos e inventário do currículo em arquivo dentro de `dados/`

## Status
Aceita

## Contexto
O PLANO (seções 2.2, 7.2 e 7.3) previa `conteudo/blocos.yaml` e `conteudo/inventario.yaml` na
raiz do repositório. Os dois arquivos carregam o currículo real do Filipe: cargos, empresas,
períodos, redação dos bullets e projetos. O repositório é público e a política de privacidade
proíbe dado pessoal em arquivo versionado. A pergunta Q9 era se esse conteúdo mora em arquivo
ou no banco.

## Decisão
Blocos e inventário moram em arquivo YAML em `dados/conteudo/`, que está fora do git. São
gerados por `make conteudo` a partir do guia apontado por `PLEITO_GUIA`, sem IA, e validados
por schema pydantic em `src/conteudo/modelo.py`. O gravador recusa qualquer destino que resolva
fora de `dados/` e grava com permissão 600. Os testes usam só o guia fictício de
`tests/fixtures/guia_ficticio.md`. O cabeçalho do currículo (contato) não é decomposto.

O banco fica para a fase 7, quando houver versionamento de currículo por vaga.

## Consequências
- o repositório versiona só o schema, o parser e a configuração em `config/conteudo.yaml`
- uma tecnologia citada no Sobre ou em bullet sem âncora em bullet de experiência ou projeto
  impede a geração, o que mantém a regra de não invenção desde a origem
- PT e EN precisam ter a mesma estrutura (mesmas entradas e mesma quantidade de bullets);
  divergência recusa o guia em vez de casar blocos errados
- ids de bullet são posicionais (`<bloco>_<n>`); reordenar bullets no guia muda os ids
- famílias por bullet ficam vazias até o Filipe ou a F2.x preenchê-las
