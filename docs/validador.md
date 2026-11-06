# Validador do currículo

O validador roda em código, sem IA, sobre o `.tex` gerado e, quando existe, o PDF. Devolve uma lista de violações; cada uma traz `codigo` (V<n>), `trecho` (o pedaço do documento que motivou a recusa, no máximo `conteudo.trecho_max_chars`) e `sugestao` (uma frase curta). É o formato que o laço de geração (F3.3) devolve à IA.

Entrada das regras de conteúdo (V6 a V9 e V11 a V21): o `.tex`, o inventário e um `ContextoConteudo` com os blocos, a vaga (`Vaga`: empresa, descrição e título), os padrões de escrita, o cabeçalho e a formação travados e o idioma escolhido. `validar_curriculo` e `exigir_valido` exigem o `contexto` (sem ele a chamada nem existe, para um currículo não passar sem as regras de conteúdo). `validar_arquivos` e `exigir_arquivos_validos` são as regras do F2.3 com o PDF, e `validar_fonte` e `exigir_fonte_valida` só as da fonte; nenhum deles roda V6 a V21 e nenhum serve de aprovação final. O texto da vaga não define regra; só entra como comparação (V12 e V13), que pode recusar um trecho, mas nunca liberar um. Por isso "ignore as regras" dentro de uma vaga não altera nenhum veredito.

Limites, listas e nomes de seção vêm de `config/validador.yaml` (chave `conteudo`) e de `config/padroes_curriculo.yaml`; o código não carrega número nem lista. Cada regra é uma função em `REGRAS` (`src/validador/conteudo.py`) e tem teste que falha sem ela (`tests/test_validador_conteudo_integracao.py`).

| Código | O que recusa | Onde está a regra |
| --- | --- | --- |
| V1 | `pdflatex` com erro | F2.6, ainda não existe |
| V2 | PDF com mais de uma página | `src/validador/paginas.py`, `paginas_max` |
| V3 | caixa estourada (`Overfull` e `Underfull hbox`) | F2.6, ainda não existe |
| V4 | título e data da mesma entrada em linhas diferentes | F2.6, ainda não existe |
| V5 | caixas de texto sobrepostas no PDF | F2.6, ainda não existe |
| V6 | preâmbulo diferente do template do idioma; só `linespread` e margens podem variar | `regras_estrutura.validar_preambulo`, `conteudo.preambulo.parametros_livres` |
| V7 | nome, cidade, email, telefone, link, instituição ou período diferentes do base, ou texto extra no cabeçalho | `regras_estrutura.validar_cabecalho` |
| V8 | experiência com cargo, empresa ou período diferente dos blocos, fora da ordem, repetida, inventada ou removida | `regras_experiencias.validar_experiencias` |
| V9 | experiência sem nenhum bullet | `regras_experiencias.validar_experiencias_vazias` |
| V10 | `\tech{}` ou menção a tecnologia fora do inventário | `src/validador/tecnologias.py`, `tecnologias_conhecidas` |
| V11 | número que não existe nos blocos, no cabeçalho ou no inventário (métrica inventada) | `regras_fidelidade.validar_numeros` |
| V12 | nome da empresa da vaga fora dos títulos vindos dos blocos | `regras_fidelidade.validar_empresa_da_vaga`, `conteudo.empresa_da_vaga` |
| V13 | trecho do Sobre ou de bullet com N palavras seguidas iguais ao anúncio | `regras_fidelidade.validar_copia_da_vaga`, `conteudo.copia_da_vaga.palavras` |
| V14 | seção nova, ausente, repetida, fora de ordem ou proibida (Skills), título fora do idioma, negrito fora de `\tech{}` | `regras_estrutura.validar_estrutura`, `conteudo.secoes`, `secoes_proibidas` e `conteudo.negrito` |
| V15 | menos de 3 ou mais de 4 projetos, ou "Mais projetos" fora do fim | `regras_experiencias.validar_projetos`, `conteudo.projetos` |
| V16 | `&`, `_`, `#` ou `$` sem escape no corpo (URL exibida, título, bullet) | `regras_estrutura.validar_escapes`, `conteudo.escapes.simbolos` |
| V17 | LaTeX perigoso: comando, ambiente, pacote, classe, link ou medida fora da allowlist | `src/validador/latex.py`, `latex` |
| V18 | fonte, linespread ou margem abaixo do mínimo por idioma | F2.6, ainda não existe |
| V19 | `babel` de outro idioma ou texto cujas palavras-marca são de outro idioma | `regras_estrutura.validar_idioma`, `conteudo.idioma.marcadores` |
| V20 | bullet ou Sobre sem o terminador, ou com caractere proibido de pontuação | `regras_fidelidade.validar_pontuacao`, `pontuacao` dos padrões |
| V21 | verbo ou expressão de senioridade inflada sem base nos blocos | `regras_fidelidade.validar_senioridade`, `senioridade_inflada` dos padrões |
| V22 | bullet que perde ou troca o fato do bloco | F5.3, revisão cruzada, ainda não existe |

Fora da lista V<n>, o F2.3 também recusa travessão, caractere invisível e alfabeto fora do permitido (`caracteres` em `config/validador.yaml`), sem código.

## Decisões

- "Mais projetos" ausente passa em V15: o template atual não o gera. Presente, precisa ser o último e não conta como projeto.
- V8 trata a ordem dos blocos como a ordem cronológica e recusa experiência removida, porque a ordem de corte (a sequência de cortes que o código aplica, do menor ao maior impacto, quando o currículo passa de uma página; PLANO 7.6 e `ordem_de_corte` dos padrões) nunca remove experiência.
- V12 ignora o nome da empresa quando ele aparece só nos títulos e no cabeçalho vindos dos blocos (o candidato pode ter trabalhado na empresa da vaga); citado no Sobre ou em bullet, recusa.
- V19 compara palavras-marca por trecho de texto, não pelo documento inteiro, para uma frase em outro idioma não se diluir no resto.
- Número escrito por extenso ("trezentos") não é visto por V11.
