# Validador do currículo

O validador roda em código, sem IA, sobre o `.tex` gerado e, quando existe, o PDF. Devolve uma lista de violações; cada uma traz `codigo` (V<n>), `trecho` (o pedaço do documento que motivou a recusa, no máximo `conteudo.trecho_max_chars`) e `sugestao` (uma frase curta). É o formato que o laço de geração (F3.3) devolve à IA.

Entrada das regras de conteúdo (V6 a V9 e V11 a V21): o `.tex`, o inventário e um `ContextoConteudo` com os blocos, a vaga (`Vaga`: empresa, descrição e título), os padrões de escrita, o cabeçalho e a formação travados e o idioma escolhido. `validar_curriculo` e `exigir_valido` exigem o `contexto` (sem ele a chamada nem existe, para um currículo não passar sem as regras de conteúdo). `validar_arquivos` e `exigir_arquivos_validos` são as regras do F2.3 com o PDF, e `validar_fonte` e `exigir_fonte_valida` só as da fonte; nenhum deles roda V6 a V21 e nenhum serve de aprovação final. O texto da vaga não define regra; só entra como comparação (V12 e V13), que pode recusar um trecho, mas nunca liberar um. Por isso "ignore as regras" dentro de uma vaga não altera nenhum veredito.

Limites, listas e nomes de seção vêm de `config/validador.yaml` (chave `conteudo`) e de `config/padroes_curriculo.yaml`; o código não carrega número nem lista. Cada regra é uma função em `REGRAS` (`src/validador/conteudo.py`) e tem teste que falha sem ela (`tests/test_validador_conteudo_integracao.py`).

| Código | O que recusa | Onde está a regra |
| --- | --- | --- |
| V1 | `pdflatex` com erro: cada linha `!` do `.log` vira uma violação com as linhas seguintes; log informado e ausente, ilegível ou maior que o limite também recusa | `layout_log.validar_compilacao`, `layout.log` |
| V2 | PDF com mais de uma página | `src/validador/paginas.py`, `paginas_max` |
| V3 | caixa estourada (`Overfull` acima de `overfull_max_pt`, `Underfull` acima de `underfull_badness_max`), com página, medida e o trecho da linha | `layout_log.validar_caixas`, `layout.log` |
| V4 | título e data da mesma entrada em linhas diferentes, ou entrada que não aparece no texto do PDF | `layout_pdf.validar_titulo_e_data`, `layout.pdf.tolerancia_de_linha_pt` |
| V5 | caixas de texto sobrepostas no PDF | `layout_pdf.validar_sobreposicao`, `layout.pdf` |
| V6 | preâmbulo diferente do template do idioma; só `linespread` e margens podem variar | `regras_estrutura.validar_preambulo`, `conteudo.preambulo.parametros_livres` |
| V7 | nome, cidade, email, telefone, link, instituição ou período diferentes do base, ou texto extra no cabeçalho | `regras_estrutura.validar_cabecalho` |
| V8 | experiência com cargo, empresa ou período diferente dos blocos, fora da ordem, repetida, inventada ou removida | `regras_experiencias.validar_experiencias` |
| V9 | experiência sem nenhum bullet | `regras_experiencias.validar_experiencias_vazias` |
| V10 | `\tech{}` fora do inventário, ou tecnologia do dicionário citada sem evidência no banco de tecnologias (evidência fraca vira indício) | `src/validador/tecnologias.py`, `tecnologias_conhecidas`, `config/tecnologias_conhecidas.yaml` |
| V11 | número que não existe nos blocos, no cabeçalho ou no inventário (métrica inventada) | `regras_fidelidade.validar_numeros` |
| V12 | nome da empresa da vaga fora dos títulos vindos dos blocos | `regras_fidelidade.validar_empresa_da_vaga`, `conteudo.empresa_da_vaga` |
| V13 | trecho do Sobre ou de bullet com N palavras seguidas iguais ao anúncio (palavras do vocabulário do currículo não contam) | `regras_fidelidade.validar_copia_da_vaga`, `conteudo.copia_da_vaga.palavras` |
| V14 | seção nova, ausente, repetida, fora de ordem ou proibida (Skills), título fora do idioma, negrito fora de `\tech{}` | `regras_estrutura.validar_estrutura`, `conteudo.secoes`, `secoes_proibidas` e `conteudo.negrito` |
| V15 | menos de 3 ou mais de 4 projetos, ou "Mais projetos" fora do fim | `regras_experiencias.validar_projetos`, `conteudo.projetos` |
| V16 | `&`, `_`, `#` ou `$` sem escape no corpo (URL exibida, título, bullet) | `regras_estrutura.validar_escapes`, `conteudo.escapes.simbolos` |
| V17 | LaTeX perigoso: comando, ambiente, pacote, classe, link ou medida fora da allowlist | `src/validador/latex.py`, `latex` |
| V18 | fonte, linespread ou margem abaixo do mínimo por idioma | `layout_limites.validar_limites`, `layout.por_idioma` |
| V19 | `babel` de outro idioma ou texto cujas palavras-marca são de outro idioma | `regras_estrutura.validar_idioma`, `conteudo.idioma.marcadores` |
| V20 | bullet ou Sobre sem o terminador, ou com caractere proibido de pontuação | `regras_fidelidade.validar_pontuacao`, `pontuacao` dos padrões |
| V21 | verbo ou expressão de senioridade inflada sem base nos blocos nem no vocabulário | `regras_fidelidade.validar_senioridade`, `senioridade_inflada` dos padrões |
| V22 | bullet que perde ou troca o fato do bloco | F5.3, revisão cruzada, ainda não existe |

Fora da lista V<n>, o F2.3 também recusa travessão, caractere invisível e alfabeto fora do permitido (`caracteres` em `config/validador.yaml`), sem código.

## Layout do PDF (V1, V3, V4, V5, V18)

`validar_curriculo` recebe também `log` (o `.log` do `pdflatex`); sem ele, o validador usa `cv.log` ao lado do PDF. Havendo PDF, o log é obrigatório: ausente, ilegível, maior que o limite ou mais velho que o PDF (diferença acima de `layout.log.defasagem_max_s`, sinal de log de outra compilação) recusa por V1. V3 lê também `Overfull` e `Underfull \vbox`, com limites próprios. Cada regra é uma função em `REGRAS_DE_LAYOUT` (`src/validador/layout.py`) e tem teste que falha sem ela (`tests/test_validador_layout.py`, e com `pdflatex` real em `tests/test_validador_layout_real.py`, marcador `latex`). Todos os limites ficam na chave `layout` de `config/validador.yaml`.

- O log é dado, nunca instrução: lido com no máximo `layout.log.tamanho_max_bytes`, decodificado com substituição, sem executar nada; texto de comando LaTeX dentro dele é só texto. No máximo `erros_max` erros e `caixas_max` caixas por validação.
- V4 e V5 leem o PDF com o pypdf. V4 acha a entrada (título, complemento e data de cada `\hfill`) no texto do PDF ignorando espaço, acento e pontuação, e recusa se as linhas diferem mais que a tolerância (título que quebrou em duas linhas empurra a data para baixo). Entrada que não aparece no PDF também recusa, para PDF e fonte não divergirem em silêncio.
- V5 mede cada trecho de texto pelas larguras de glifo da fonte do PDF (`/Widths`), com a largura média de `largura_sem_metrica_em` quando a fonte não traz medida. A altura da caixa vem de `ascendente_em` e `descendente_em`. O pypdf entrega a posição horizontal só no começo de cada linha; por isso o código acompanha `Td`, `Tm`, `Tf`, `Tj` e `TJ` e soma as larguras. Quebras de linha do próprio TeX nunca se tocam (o TeX impõe o `\lineskip`), então V5 pega sobreposição criada por espaço negativo ou por PDF fora do pdflatex.
- V18 lê o preâmbulo do `.tex`: tamanho da classe (`fonte_padrao_pt` quando a classe não traz), `\linespread` e as chaves de margem do `geometry` (`chaves_de_margem`), convertidas para mm pela tabela `latex.medidas.unidades_mm`. Os mínimos são por idioma em `layout.por_idioma`.
- PDF ilegível ou ausente não dispara V4 nem V5 (V2 já recusa). PDF legível cujo conteúdo não dá para medir recusa: coordenada infinita ou `nan`, estouro numérico, recursão e mais de `layout.pdf.caixas_max` caixas. O PDF é lido uma vez por validação, para V4 e V5.

## Níveis, evidência e vocabulário (F2.8)

Toda regra tem um nível em `niveis` de `config/validador.yaml`, e a ausência de uma regra na lista é erro de configuração:

| Nível | Efeito |
| --- | --- |
| `bloqueia` | recusa: `aprovado` fica falso, `exigir_*` levanta `CurriculoInvalido` |
| `indicio` | não recusa; vai no resultado para a revisão do Filipe e a rubrica do F3.3 |
| `ok` | não recusa nem pede revisão; fica registrado com a evidência que salvou |

- O nível da configuração é um teto: a regra pode decidir um nível menor (tecnologia com evidência fraca é `indicio`, com evidência forte é `ok`), nunca maior. Regra em `ok` na configuração registra o achado com a evidência "regra em ok na configuracao".
- Segurança nunca desce: `REGRAS_DE_SEGURANCA` (`src/validador/resultado.py`: página, LaTeX, alfabeto, caractere invisível, cabeçalho, empresa da vaga, compilação e escape) fica em `bloqueia`. Config que rebaixa uma delas não carrega (`ValidationError`), e `aplicar_niveis` força `bloqueia` mesmo se a regra pedir menos. Os dois têm teste (`tests/test_validador_niveis.py`).
- Começam em `indicio` só as regras de estilo e de semelhança: V13 (cópia da vaga) e V20 (pontuação). Senioridade (V21), número (V11), tecnologia (V10) e as demais ficam em `bloqueia` por configuração, não por trava no código: a configuração pode rebaixá-las, a tabela de níveis do repositório é fixada por teste (`test_niveis_do_repositorio_sao_os_combinados`) e mudar isso é decisão de produto.
- Resultado: `violacoes` traz tudo; `bloqueios`, `indicios` e `salvos` separam por nível; `regras_bloqueadas` é o que o laço do F3.3 corrige. Cada `Violacao` tem `codigo`, `nivel`, `trecho`, `regra`, `sugestao` e `evidencia` (o que faltou ou o que salvou).
- O runner do F2.4 só conta `bloqueia` como falha de regra.

### De onde vem cada evidência

| Evidência | Fonte | Gerado por |
| --- | --- | --- |
| tecnologia com âncora | `dados/conteudo/tecnologias.yaml`: cada tecnologia do inventário aprovado (origem `inventario`, âncora e fonte) e cada tecnologia sugerida pelo F2.7 que o Filipe aprovou (`status: aprovada`; pendente e rejeitada não contam; origem `linguagem`, `topic`, `readme` ou `pagina`, projeto e URL pública) | `make validador-dados` |
| vocabulário do currículo | `dados/conteudo/vocabulario.yaml`, `pt` e `en` separados: verbos de abertura de bullet, siglas, termos de domínio (n-gramas dos blocos sem palavra vazia nas pontas) e nomes de projeto; termo ou sigla que é ou contém nome do dicionário de tecnologias nunca entra | `make validador-dados` |

`make validador-dados` lê `dados/conteudo/blocos.yaml` e `inventario.yaml` (rode `make conteudo` antes) e, quando existir, `sugestoes.yaml`. Os dois arquivos ficam em `dados/`, com permissão 0600, e nunca entram no git; os testes usam fixture fictícia. A força de cada origem (`forte` ou `fraca`) e o tamanho do n-grama estão em `tecnologias.forca_por_origem` e `dados.vocabulario`.

Tecnologia citada em texto puro (V10):

1. nome do inventário aprovado: passa sem registro;
2. evidência forte no banco: `ok`; só evidência fraca: `indicio`; nenhuma ou banco ausente: `bloqueia`;
3. o vocabulário nunca salva tecnologia do dicionário: só o banco de evidências a libera, mesmo que o nome apareça num nome de projeto, sigla ou termo do vocabulário;
4. `\tech{}` fora do inventário bloqueia sempre, com ou sem evidência.

O dicionário amplo (`config/tecnologias_conhecidas.yaml`, por categoria) soma-se a `tecnologias_conhecidas` e casa sem diferenciar caixa (falha fechada). Só os nomes de `tecnologias.palavras_comuns` (Go, Spring, Express e outros que são palavra comum em pt ou en) saem da regra: na caixa exata do dicionário valem como tecnologia; em outra caixa viram `indicio` ("palavra comum"), nunca `ok`, nem com evidência no banco. `tecnologias.evidencias_mostradas` limita quantas evidências aparecem no campo `evidencia`. O gerador (F3.1) continua sem banco e por isso recusa tecnologia do dicionário citada em texto puro.

V13 e V21 com vocabulário: palavras cobertas por termo do vocabulário do idioma do documento não contam para as N palavras da cópia (só recusa quando sobram N palavras próprias), e termo de senioridade que está no vocabulário vira `ok`. Tecnologia não entra nessa exceção (acima). Verbo que falta no vocabulário e nos blocos (`liderei`) continua bloqueando.

### Relatório de calibração

`make validador-calibrar` roda o validador sobre o conjunto do F2.4 (armadilhas fictícias e, se existirem, as vagas de `dados/avaliacao/vagas/`) e grava `dados/validador/calibracao/<data>_calibracao.json` (0600, sem texto de vaga nem trecho do currículo). Sai com 0 dentro das metas e 1 fora.

- Falso positivo por regra: o currículo de referência de cada entrada (blocos sem alteração) não pode acusar nada. Taxa = amostras acusadas por `bloqueia` ou `indicio` dividido pelas amostras boas.
- Falso negativo por regra: para cada regra de `calibracao.injecoes`, o termo ruim da entrada (proibido de tecnologia, número ou palavra, empresa da vaga, ou o começo do anúncio) é injetado no Sobre; a regra que não acusa (ou só registra `ok`) é falso negativo.
- Metas em `calibracao.metas` (`falso_positivo_max` e `falso_negativo_max`), com `calibracao.por_regra` para regra específica. `calibracao.palavras_extras_do_anuncio` e `calibracao.caracteres_fora_do_texto` ajustam o trecho do anúncio injetado; `calibracao.injecoes.<regra>.ignorar` tira da conta um termo que não é afirmação sozinha (por exemplo o fragmento `lideran`, que só serve de verificação de saída).
- Regra sem injeção (layout, LaTeX, alfabeto, cabeçalho e as demais) aparece em `sem_injecao`: o falso negativo dela não é medido aqui.
- Como ler: `regras.<nome>.falso_positivo` e `falso_negativo` trazem `erros`, `total`, `taxa`, `meta` e `dentro_da_meta`; `fora_da_meta` lista as regras que estouraram e `veredito` é `dentro_das_metas` ou `fora_das_metas`. Falso positivo alto pede rebaixar a regra para `indicio` ou ampliar o vocabulário; falso negativo alto pede ampliar dicionário ou lista de verbos.
- Achado do conjunto atual: "sênior" e "senior" ficam fora de `senioridade_inflada` (`config/padroes_curriculo.yaml`, F3.0), então V21 não pega a palavra solta e o falso negativo de senioridade passa da meta.

## Decisões

- "Mais projetos" ausente passa em V15: o template atual não o gera. Presente, precisa ser o último e não conta como projeto.
- V8 trata a ordem dos blocos como a ordem cronológica e recusa experiência removida, porque a ordem de corte (a sequência de cortes que o código aplica, do menor ao maior impacto, quando o currículo passa de uma página; PLANO 7.6 e `ordem_de_corte` dos padrões) nunca remove experiência.
- V12 ignora o nome da empresa quando ele aparece só nos títulos e no cabeçalho vindos dos blocos (o candidato pode ter trabalhado na empresa da vaga); citado no Sobre ou em bullet, recusa.
- V19 compara palavras-marca por trecho de texto, não pelo documento inteiro, para uma frase em outro idioma não se diluir no resto.
- Número escrito por extenso ("trezentos") não é visto por V11.
