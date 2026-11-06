---
name: auditoria-juridica
description: "Uso manual: só quando pedida pelo nome ou numa revisão jurídica explícita. Audita o repositório de código de um produto de software contra as exigências jurídicas brasileiras: compara o que o sistema coleta, registra e permite (cookies, SDKs, logs, formulários, exclusão de conta, cancelamento, verificação de idade) com o que os Termos e a Política de Privacidade declaram. Use para \"auditoria LGPD do código\", \"estamos prontos para lançar?\" ou \"compliance do app\"."
---

# Auditoria jurídica do produto

Siga primeiro as regras comuns em `../founder-juridico-br/referencias/REGRAS.md` (perguntas de triagem, como citar, aviso legal).

## Fluxo
1. Localize no repositório os Termos e a Política publicados (ou as URLs) e leia-os.
2. Varra o código:
   - dados coletados: modelos, schemas, formulários, eventos de analytics;
   - SDKs de terceiros e onde enviam dados (analytics, crash, ads, pagamento, IA);
   - cookies e armazenamento local, e se esperam consentimento;
   - logs de acesso: campos, retenção, controle de acesso (Marco Civil, art. 15);
   - funcionalidades de exportar dados, excluir conta e cancelar assinatura;
   - verificação de idade e configurações para menores;
   - região de hospedagem (transferência internacional).
3. Cruze com `checklist-lancamento.md` e com os guias das outras skills (`../<skill>/guia.md`).
4. Entregue uma tabela `achado | evidência (arquivo:linha) | exigência legal | gravidade | correção`. Separe divergências entre documento e código; elas são as mais graves (LGPD, art. 6º, VI; CDC, art. 30).
