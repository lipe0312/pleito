# Regras comuns a todas as skills

Estas regras valem para qualquer skill do plugin. Os caminhos são relativos à raiz do plugin.

## Antes de escrever
Pergunte só o que faltar sobre o produto:
- B2C, B2B ou ambos? (define se o CDC se aplica — `referencias/cdc-8078-1990.md#art-2`)
- Que dados pessoais coleta, para quê, com quem compartilha, onde hospeda (fora do Brasil?)
- Cobra? Assinatura recorrente, teste grátis, renovação automática?
- Usuários publicam conteúdo, há chat, marketplace, IA gerando conteúdo?
- Pode ser usado por menores de 18 ("acesso provável")?
- Quem escreveu o código (sócios, CLT, PJ, freelancer, open source)?

Se a pessoa estiver num repositório do produto, prefira verificar no código a perguntar.

## Citações
- Cite um artigo apenas se ele estiver em `referencias/` (índice: `referencias/indice.md`),
  no formato "LGPD, art. 18", com o link `fonte` do frontmatter. Leia o trecho antes de
  citar; não parafraseie de memória.
- O que não estiver em `referencias/` vai marcado como **"não verificado no acervo"**, com a
  URL oficial (ex.: Lei 9.609/1998, LC 182/2021, resoluções da ANPD).
- Não invente jurisprudência. A única tese incluída é a do STF sobre o art. 19 do Marco Civil
  (`referencias/stf-tema-987.md`), que vem truncada na fonte; avise isso ao usar.
- Informe a data `baixado_em` dos textos: leis mudam.

## Ao entregar
Escreva documentos em português claro, com as cláusulas restritivas destacadas
(CDC, arts. 46 e 54). Termine sempre com:
1. riscos por gravidade;
2. pontos que dependem de decisão de negócio;
3. o que validar com advogado. **Este plugin é informativo e não substitui assessoria
   jurídica.**
