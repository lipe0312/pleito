# Inventário de projetos sincronizado com GitHub e portfólio

O inventário e os blocos do currículo (ADR 0021) nascem do guia. Este fluxo (item F2.7, PLANO
7.2, 7.3 e 4.10) acrescenta o que o Filipe tem de verdade no GitHub e no portfólio, como
**sugestão** que ele aprova. Nada entra em `blocos.yaml` nem em `inventario.yaml` sozinho.

## Comandos

- `make conteudo-sincronizar`: lê as fontes e grava `dados/conteudo/sugestoes.yaml` (permissão
  600, fora do git). Não escreve em `blocos.yaml` nem em `inventario.yaml`. Rotina semanal
  declarada em `config/limites.yaml` (`conteudo_sincronizar`); o plist continua manual (M3).
- `make conteudo-aprovar ARGS=--listar`: mostra as pendentes com o id de cada uma.
- `make conteudo-aprovar ARGS="--id sug_xxx --por Filipe"`: aprova e grava.
- `make conteudo-aprovar ARGS="--id sug_xxx --por Filipe --rejeitar --motivo 'projeto de disciplina'"`.

A tela `/projetos` do painel (F3.4) faz o mesmo por botão: aprovar grava quem e quando, rejeitar
exige motivo, os dois por `POST` com token CSRF. O comando continua valendo.

## De onde vem cada sugestão

Tudo em `config/conteudo.yaml`, bloco `sincronizacao`:

| Sugestão | Quando nasce | O que a aprovação grava |
| --- | --- | --- |
| `projeto_novo` | repositório público (ou página) que nenhum bloco de projeto aponta | bloco `proj_<nome>` com nome, descrição e link em todos os idiomas |
| `tecnologia_nova` | tecnologia achada no projeto sem âncora do tipo projeto para ele | âncora `{tipo: projeto, ref, fonte: URL}` no inventário |
| `projeto_arquivado` | bloco aponta para repositório arquivado | só registra a ciência |
| `projeto_sumido` | bloco aponta para repositório que não está mais na listagem completa | só registra a ciência |

Toda `tecnologia_nova` carrega âncora tipo projeto com a URL pública do repositório (montada de
`github.url_publica` e do usuário, nunca do que a API devolve) ou da página. O schema recusa a
sugestão sem isso. Aprovar tecnologia exige o bloco do projeto: aprove o `projeto_novo` antes.

Projeto já no guia é reconhecido pelo link do bloco (sem esquema, `www`, barra final ou caixa).
Sugestão rejeitada não volta, e rejeitar o projeto cala as tecnologias dele.

## Como a tecnologia é extraída (sem IA)

Dicionário `sincronizacao.dicionario`: cada tecnologia tem `linguagens`, `topics`, `termos` e
`requer`.

- **GitHub**: linguagem (endpoint de linguagens) ou topic do repositório bastam. Termo do README
  só confirma quando a tecnologia lista em `requer` outra que linguagem ou topic já sustentam
  (Maven só com Java). README sozinho nunca cria tecnologia.
- **Portfólio**: termo no texto visível da página, fora de script, estilo e comentário.
- Em ambos, frase que casa `padroes_instrucao` (ignore, adicione, inventário, prompt, comando,
  senha...) é descartada antes de procurar termos.

## Segurança

- README, descrição, topics, homepage e página são texto não confiável: nunca viram comando, URL
  a requisitar, caminho de arquivo ou instrução. A homepage é só guardada, nunca lida.
- Só os domínios de `github.dominios` e `portfolio.dominios` são requisitados, em https e sem
  seguir redirect. Fora disso a leitura é recusada antes da requisição.
- `robots.txt` é respeitado no portfólio (`respeitar_robots`). Na API do GitHub fica desligado
  de propósito: é a API documentada, sem token, limitada a 60 requisições por hora, e cada
  consulta de robots gastaria cota.
- Exceção explícita à `config/fontes.yaml`: aquela allowlist é de coleta de vaga; este fluxo lê o
  perfil público do próprio Filipe (GitHub e portfólio), então a allowlist própria mora em
  `config/conteudo.yaml` (`github.dominios`, `portfolio.dominios`) e vale só para
  `src/conteudo/leitor.py`. Nenhum outro módulo pode usar essa lista, e o coletor continua
  restrito a `fontes.yaml`.
- O corpo é lido em stream e a leitura para ao passar `resposta_max_bytes` (ou recusa antes, se o
  `Content-Length` já passa do limite).
- Descrição do repositório e `<meta description>` da página passam pelo mesmo filtro de frase de
  instrução do README; o que sobra é limpo e cortado.
- Limites de topics, linguagens, padrão de nome e cabeçalhos `Accept` ficam em `config/conteudo.yaml`.
  A porta 443 (https) fica no código por ser semântica do protocolo, não política.
- `requisicoes_max` corta a execução; cortada, a listagem fica `completo: false` e nenhum projeto
  é declarado sumido. Ritmo vem de `PLEITO_RATE_LIMIT_RPS`.
- Descrição é limpa de caractere de controle e cortada em `descricao_max_chars`; nome de
  repositório fora do padrão é ignorado. O gerador ainda escapa tudo contra LaTeX.
- Erro da API (limite, 403, rede) aborta sem gravar nada.
- Resíduo aceito: página do portfólio que afirma uma tecnologia em frase comum vira sugestão. A
  aprovação humana é a barreira, e a sugestão mostra a evidência (`pagina:<termo>`).

## Preencher o portfólio (manual do Filipe)

A lista `sincronizacao.portfolio.paginas` e `portfolio.dominios` estão vazias: o código funciona
sem elas. Quando o site existir, preencher com uma entrada por projeto:

    dominios: [meu-portfolio.example]
    paginas:
      - {url: https://meu-portfolio.example/projeto-poo, nome: Projeto POO}

O domínio precisa estar em `dominios`; o `nome` vira o id `proj_<nome>`.

## Limitações conhecidas

- `make conteudo` regera `blocos.yaml` e `inventario.yaml` do guia e apaga o que foi aprovado
  aqui; depois dele, rode `make conteudo-sincronizar` e aprove de novo (as aprovadas voltam como
  pendentes porque o bloco sumiu).
- Dois repositórios cujos nomes diferem só por pontuação geram o mesmo id de projeto.
