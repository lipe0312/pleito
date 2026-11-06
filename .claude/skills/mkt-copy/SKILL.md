---
name: mkt-copy
description: Escreve e revisa textos pt-BR e en do pleito que alguém lê — telas e erros do painel, email de resumo diário, respostas padrão e rascunhos para pergunta nova de formulário, slots do currículo, README e textos de portfólio — com regras de clareza, prova e honestidade (nada fora do inventário). Use ao criar ou revisar qualquer texto visível ao Filipe ou a um recrutador. Para página inteira, combina com copywriting, copy-editing e cro.
---

# Texto que funciona (pt-BR e en)

Contexto: `.agents/product-marketing.md` (quem lê, tom, o que pode ser afirmado). Não peça ao Filipe o que já está lá.

## Dois leitores, regras diferentes
- **O Filipe** (painel, resumo diário, pendência): quer decidir rápido. Diga o que aconteceu, o que precisa dele e o que acontece se não fizer nada.
- **Recrutador ou ATS** (slots do currículo, resposta padrão, rascunho de pergunta nova): quer prova. Só fato que está nos blocos e no inventário de `dados/conteudo/`; o validador recusa o resto.

## Regras (nesta ordem)
1. **Específico > genérico.** "3 vagas novas acima de 80, 1 pendência na Gupy" > "Novidades no painel". Números reais do sistema, nunca inventados.
2. **Honestidade do currículo.** Nenhuma tecnologia, cargo, prazo ou resultado que não esteja nos blocos ou no inventário. Sem exagero de senioridade.
3. **Uma ideia por bloco.** Título ≤ 8 palavras; linha de resumo ≤ 20.
4. **Verbo no começo, voz ativa.** "Aprove a versão" > "Aprovação da versão". No currículo, verbo no passado com resultado.
5. **Erro diz o que fazer.** "Token do Gmail ausente: rode `make gmail-autorizar`" > "Erro de autenticação".
6. **Sem jargão de IA nem de coach:** proibido "revolucione", "potencialize", "apaixonado por", "sinergia", "solução completa". Sem travessão (o validador recusa no currículo; no resto, prefira vírgula ou ponto).
7. **Idioma da vaga.** Vaga em inglês → slot e resposta em inglês; painel e resumo sempre em pt-BR.
8. **Nada sensível no texto.** Telefone, endereço, CPF, dado de diversidade só com confirmação explícita (plano 18.3) e nunca em prompt de LLM.

## Fórmulas rápidas
- Linha do resumo diário: **[quantas] + [o quê] + [o que fazer]** → "2 vagas prontas para revisar · 1 resposta de empresa em Entrevista"
- Bullet de currículo: **verbo + o que fez + com o quê (inventário) + resultado medido**
- Rascunho de pergunta nova: responde a pergunta na primeira frase, uma evidência dos blocos, fecha. ≤ 120 palavras.

## Revisão de texto existente
1. Liste os textos (`arquivo:linha`).
2. Para cada um: nota 1–5 em clareza e especificidade; reescreva os 3 piores.
3. Entregue 2–3 variações para o título ou assunto principal, com o porquê.

Página inteira (README, portfólio) → skills `copywriting`, `copy-editing`, `cro`. Ação principal → `mkt-cta`. Texto para o LinkedIn → `linkedin-agent:li-post` e `linkedin-agent:li-human`, sempre publicado à mão.
