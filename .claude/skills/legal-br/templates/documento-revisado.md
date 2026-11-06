# Modelo - documento revisado

Nome do arquivo de saída: `<nome-do-original>-REVISADO-AAAA-MM-DD.md`

---

# Revisão - [TÍTULO DO DOCUMENTO]

| | |
|---|---|
| Documento de origem | `[ARQUIVO]` |
| Tipo | [contrato / política / termo / regulamento / proposta] |
| Partes | [QUEM E QUEM] |
| Solicitante | [PREENCHER] |
| Data da revisão | [AAAA-MM-DD] |

## 1. Resumo executivo

Três a cinco linhas: o que é o documento, em que estado chegou e qual a recomendação geral.

**Situação:** [pronto para uso / pronto após ajustes / precisa de reescrita / precisa de advogado antes de qualquer uso]

| Severidade | Quantidade |
|---|---|
| Risco alto | [N] |
| Risco médio | [N] |
| Risco baixo | [N] |
| Pendências de validação | [N] |

## 2. Contexto e premissas

**Fatos confirmados** - o que veio do documento ou foi informado.

- [FATO]

**Hipóteses de trabalho** - o que foi assumido por ausência de informação. Se alguma estiver errada, a análise muda.

- [HIPÓTESE]

## 3. Análise cláusula a cláusula

Repita o bloco abaixo para cada cláusula. Cláusula sem problema também entra, como "sem apontamento".

### Cláusula [N] - [TÍTULO]

**Texto original**

> [TRANSCRIÇÃO LITERAL]

**Classificação:** FATO LEGAL | INTERPRETAÇÃO | RECOMENDAÇÃO | RISCO | PENDÊNCIA DE VALIDAÇÃO

**Risco:** Alto | Médio | Baixo | -

**Apontamento**

[O problema, em linguagem direta. Se não houver, escrever "Sem apontamento."]

**Fundamento**

- Norma: [LEI, ARTIGO]
- Verificado em: `fontes/[CAMINHO]` ou [URL OFICIAL]
- Data da verificação: [AAAA-MM-DD]
- Transcrição: > [TEXTO LEGAL LITERAL]

**Redação proposta**

> [TEXTO SUBSTITUTIVO]

**O que muda na prática**

[Efeito concreto da alteração.]

---

## 4. Cláusulas ausentes

Pontos que o documento deveria tratar e não trata.

| Tema | Por quê | Fundamento | Severidade |
|---|---|---|---|
| [TEMA] | [MOTIVO] | [NORMA + FONTE] | [Alta/Média/Baixa] |

## 5. Campos a preencher

Dados que dependem da empresa ou do cliente e não podem ser inventados.

- [ ] `[PREENCHER]` - [ONDE APARECE E O QUE É]

## 6. Requisitos para implementação

Quando o documento estiver ligado a uma funcionalidade de software.

- [ ] [AÇÃO CONCRETA NO PRODUTO]

## 7. Pendências de validação

O que o agente **não** conseguiu confirmar. Encaminhado em `[CONSULTA-ADVOGADO-...md]`.

Se não houver nenhuma, escreva "Nenhuma - todos os pontos foram verificados em fonte oficial" e siga em frente. Não invente ressalva para preencher a seção.

| # | Questão | Por que não foi possível concluir | Impacto |
|---|---|---|---|
| 1 | [QUESTÃO] | [MOTIVO] | [IMPACTO] |

## 8. Fontes verificadas

| Norma / ato | Artigo | Onde foi verificado | Data |
|---|---|---|---|
| [NORMA] | [ART.] | `fontes/[CAMINHO]` ou [URL] | [AAAA-MM-DD] |

## 9. Documento revisado - texto integral

Versão consolidada, já com as redações propostas aplicadas e os `[PREENCHER]` marcados.

---

> **Só se houver pendência:** colar aqui o bloco de `templates/sinalizacao-revisao.md`.
>
> Documento sem pendência termina na seção 9. Sem ressalva, sem rodapé, sem aviso de autoria.
