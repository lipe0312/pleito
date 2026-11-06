# Crianças, adolescentes e uso de imagem

## Princípios

Quando menores estiverem envolvidos:
- priorize o melhor interesse;
- aplique proteção reforçada;
- minimize coleta e exposição;
- considere responsável legal;
- documente decisões relevantes.

## As três camadas

Menor em produto digital atrai três regimes ao mesmo tempo, e cada um responde uma pergunta diferente. Confundi-los é a origem da maior parte dos erros nesta área.

| Regime | Pergunta que responde | Onde conferir |
|---|---|---|
| Código Civil, arts. 3º e 4º | O menor pode contratar? | `fontes-md/leis/01-codigo-civil...md` |
| LGPD, art. 14 | Os dados dele podem ser tratados, e com que consentimento? | `fontes-md/leis/03-lgpd...md` |
| ECA e ECA Digital | O produto cumpre os deveres de proteção? | `fontes-md/leis/08-eca...md` e `fontes-md/eca-digital/` |

Um produto pode estar correto na LGPD e ilegal no Código Civil - é o caso do menor que se cadastra sozinho e paga uma inscrição.

## Capacidade civil

Antes de qualquer análise de dados, verifique se há contratação.

- Menor de 16 anos: absolutamente incapaz (Código Civil, art. 3º). Ato praticado sozinho é nulo.
- De 16 a 18 anos: relativamente incapaz (art. 4º, I). Ato praticado sem assistência é anulável.

Havendo pagamento, cadastro de menor sem representação ou assistência gera contrato que a família pode desfazer. O risco é do fornecedor.

## Dados pessoais

A análise deve considerar simultaneamente LGPD e ECA, além de orientações atuais da ANPD.

A ANPD consolidou entendimento de que hipóteses legais previstas na LGPD podem ser consideradas no tratamento de dados de crianças e adolescentes, sempre observando o melhor interesse no caso concreto. Verifique o entendimento atual antes de aplicar.

Pontos do art. 14 que costumam ser esquecidos:

- § 1º: dados de **criança** exigem consentimento específico e em destaque de pelo menos um dos pais ou do responsável.
- § 4º: proibido condicionar a participação em jogo ou aplicação ao fornecimento de dados além dos estritamente necessários.
- § 5º: o controlador deve fazer **todos os esforços razoáveis** para verificar que o consentimento partiu mesmo do responsável. Aceitar data de nascimento digitada pelo próprio menor, sem nenhuma etapa adicional, não cumpre esse dever.

Atenção à distinção legal entre criança e adolescente: o ECA, art. 2º, define criança como quem tem até 12 anos incompletos. O art. 14, § 1º, da LGPD fala em criança. Não estenda automaticamente a exigência de consentimento parental do § 1º ao adolescente sem dizer com que fundamento.

## ECA Digital - Lei nº 15.211/2025

Em vigor desde **17 de março de 2026** (art. 41-A, com a redação da Lei nº 15.352/2026). Regulamentado pelo Decreto nº 12.880/2026, em vigor desde 18 de março de 2026.

### Quem alcança

O critério do art. 5º é o produto ou serviço "direcionado a crianças e a adolescentes **ou de acesso provável por eles**". A segunda hipótese é larga e pega muito produto que não se pensa como infantil. Se a operação admite menores, o enquadramento tende a existir.

A lei não traz critério objetivo para "acesso provável". Quando o enquadramento for duvidoso e mudar o tamanho da obrigação, isso é PENDÊNCIA DE VALIDAÇÃO.

### Deveres, por capítulo

- Art. 5º: deveres de prevenção, proteção, informação e segurança, somados aos do CDC e do ECA. Inclui medidas técnicas que permitam à família prevenir uso inadequado.
- Art. 6º: dever de prevenir e mitigar risco de exposição a conteúdo de abuso sexual, violência, automutilação, jogos de azar e bebida alcoólica, publicidade predatória e pornografia.
- Arts. 10 a 15: aferição de idade. Lojas de aplicativos e sistemas operacionais aferem a faixa etária e fornecem sinal de idade por API; o fornecedor deve estar preparado para receber essa informação (art. 14). O art. 13 restringe os dados coletados para verificação de idade a essa finalidade exclusiva.
- Arts. 16 e 17: supervisão parental. Informação a pais e responsáveis em local de acesso livre, **independente da aquisição do produto**; ferramentas de supervisão; aviso visível quando ativas; limitação de tempo de uso. O art. 16, parágrafo único, exige mapeamento de risco e relatório de impacto quando o tratamento de dados de menor for além do estritamente necessário para operar o produto.

### Cuidado com o alcance da vedação de autodeclaração

Erro fácil e caro. O art. 9º, § 1º, veda a autodeclaração de idade, **mas o § 2º limita essa vedação** a conteúdo pornográfico ou de outra forma vedado em lei. No Decreto nº 12.880/2026, a mesma delimitação aparece no art. 17 (conteúdo pornográfico), art. 18 (produtos proibidos para menores) e art. 19 (rede social com conteúdo proibido).

Produto comum - reserva de quadra, agenda, loja, serviço - **não** está sob essa vedação. Dizer que o ECA Digital proíbe autodeclaração nesse caso é inventar obrigação.

O que torna a autodeclaração insuficiente em produto comum é outro fundamento, mais estreito e suficiente: a LGPD, art. 14, § 5º, somada à incapacidade civil para contratar.

## Imagem

Diferencie:
1. participação na atividade;
2. captação de imagem/voz;
3. publicação;
4. uso promocional/comercial;
5. duração e canais de uso.

Não presuma que inscrição no evento equivale automaticamente a autorização ampla e irrestrita de uso de imagem.

Fundamentos: Constituição, art. 5º, X; Código Civil, arts. 11 e 20; ECA, art. 17. Cessão descrita como universal, definitiva, irrevogável e irrestrita, sem prazo nem território, colide com o art. 11 do Código Civil e, em contrato de adesão de consumo, com o CDC, art. 51, I e IV.

A extensão máxima válida de uma autorização gratuita de imagem em contrato de adesão é tema de divergência. Delimite objeto, prazo, território e canais, e escalone a extensão quando o uso comercial for relevante.

## Produto digital

Considere:
- cadastro pelo responsável;
- vínculo responsável-menor;
- registro de aceite;
- versão do termo;
- data e hora;
- possibilidade de revogação quando juridicamente aplicável;
- restrição de visibilidade pública;
- moderação e segurança;
- informação a pais em página de acesso livre (ECA Digital, art. 16);
- ferramentas de supervisão parental e aviso quando ativas (art. 17);
- uso dos dados de verificação de idade apenas para essa finalidade (art. 13).

## Fontes

- ECA: https://www.planalto.gov.br/ccivil_03/leis/l8069.htm
- ECA Digital - Lei nº 15.211/2025: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15211.htm
- Decreto nº 12.880/2026: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/decreto/d12880.htm
- LGPD: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
- Código Civil: https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm
- ANPD: https://www.gov.br/anpd/
- ANPD - entendimento sobre tratamento de dados de crianças e adolescentes:
  https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-divulga-enunciado-sobre-o-tratamento-de-dados-pessoais-de-criancas-e-adolescentes

Cópias locais: `fontes/eca-digital/` e `fontes-md/eca-digital/`. Trate a cópia como não verificada e confirme na fonte oficial antes de citar.
