# Política de Privacidade e LGPD

## Quando a LGPD se aplica
A qualquer tratamento de dados de pessoa natural feito no Brasil, com dados coletados no
Brasil ou para oferecer serviço a quem está no Brasil, **independentemente da sede da
empresa** — LGPD, art. 3º. Exceções (uso pessoal, jornalístico, segurança pública...) —
art. 4º. Definições (dado pessoal, sensível, anonimizado, controlador, operador,
encarregado) — art. 5º.

## Os 10 princípios (art. 6º)
Finalidade, adequação, necessidade (colete o mínimo), livre acesso, qualidade,
transparência, segurança, prevenção, não discriminação e responsabilização. Desenhe o
produto em torno de "necessidade": cada campo do formulário precisa de finalidade declarada.

## Escolher a base legal de cada tratamento (art. 7º)
| Tratamento típico de SaaS | Base usual |
| --- | --- |
| Cadastro e prestação do serviço | Execução de contrato (art. 7º, V) |
| Nota fiscal, guarda de logs do Marco Civil | Obrigação legal (art. 7º, II) |
| Analytics de produto, prevenção a fraude, segurança | Legítimo interesse (art. 7º, IX; requisitos no art. 10) — documente o teste de balanceamento |
| Newsletter, marketing, cookies não essenciais | Consentimento (art. 7º, I; art. 8º) |
| Defesa em processo | Exercício regular de direitos (art. 7º, VI) |

Consentimento: livre, informado, destacado, por finalidade, revogável a qualquer momento —
art. 8º. Não use consentimento para o que é necessário ao contrato.
Dados sensíveis (saúde, biometria, religião, orientação sexual, etc.) têm hipóteses mais
restritas — art. 11. Dados anonimizados de verdade saem da LGPD — art. 12.

## Conteúdo mínimo da Política (art. 9º)
Finalidade específica; forma e duração do tratamento; identidade e contato do
controlador; uso compartilhado e com quem; responsabilidades dos agentes; direitos do
titular (art. 18) e como exercê-los. Inclua também: encarregado (art. 41), transferência
internacional (art. 33), prazos de retenção e eliminação (arts. 15 e 16), cookies.

## Direitos do titular (art. 18)
Confirmação, acesso, correção, anonimização/bloqueio/eliminação de excessivos,
portabilidade, eliminação dos dados tratados com consentimento, informação sobre
compartilhamento, revogação do consentimento. **Implemente no produto**: exportar dados,
excluir conta, canal de requisições com prazo de resposta.

## Obrigações operacionais
- **Encarregado (DPO)** com contato público — art. 41. A ANPD flexibiliza para agentes de
  pequeno porte (Resolução CD/ANPD nº 2/2022 — *não verificado no acervo*,
  https://www.gov.br/anpd).
- **Registro das operações** (ROPA) — art. 37; **relatório de impacto** quando exigido — art. 38.
- **Segurança** técnica e administrativa — art. 46; Marco Civil/Dec. 8.771, art. 13
  (controle de acesso, autenticação, inventário de acessos, criptografia).
- **Incidente**: comunicar ANPD e titulares quando houver risco ou dano relevante — art. 48.
  Prazos e formulário: Resolução CD/ANPD nº 15/2024 (*não verificado no acervo*).
- **Operadores** (cloud, e-mail, analytics, pagamento): contrato com cláusulas de proteção
  de dados; controlador e operador podem responder por danos — art. 42.
- **Transferência internacional** (AWS/GCP fora do Brasil, ferramentas americanas): só nas
  hipóteses do art. 33 (adequação, cláusulas-padrão, consentimento específico...).
  Cláusulas-padrão da ANPD: Resolução CD/ANPD nº 19/2024 (*não verificado no acervo*).
- **Crianças e adolescentes**: consentimento específico de um dos pais para dados de
  criança — art. 14, § 1º; não condicionar uso a dados além do necessário — art. 14, § 4º.
  Ver também skill `criancas-adolescentes`.

## Sanções (art. 52)
Advertência; multa de até 2% do faturamento no Brasil, limitada a R$ 50 milhões por
infração; multa diária; publicização; bloqueio ou eliminação dos dados; suspensão do
banco de dados ou da atividade. Além disso, indenização civil (art. 42) e CDC.

## Cookies
Essenciais: execução do contrato/legítimo interesse. Analytics e publicidade: normalmente
consentimento, com banner que permita **recusar** com o mesmo esforço de aceitar. Guia
orientativo de cookies da ANPD (*não verificado no acervo*).
