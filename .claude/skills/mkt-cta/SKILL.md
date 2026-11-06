---
name: mkt-cta
description: Projeta as ações principais do pleito (texto, posição, hierarquia, confirmação e microcopy de apoio) no painel local, no email de resumo diário e nas pendências manuais — aprovar versão, rejeitar com motivo, abrir vaga, copiar resposta, autorizar submit real. Use ao criar ou revisar um botão de ação principal ou uma ação irreversível.
---

# Ação principal que leva à decisão certa

## Checklist (cada ação principal)
- [ ] **Uma** ação primária por tela ou por linha; as demais são secundárias ou links
- [ ] Texto = verbo + objeto: "Aprovar esta versão", "Rejeitar com motivo", "Copiar resposta" — nunca "OK", "Enviar", "Clique aqui"
- [ ] Ação irreversível ou com efeito externo (aprovar envio, autorizar submit real) tem confirmação na própria tela, diz o efeito ("Vai enviar o PDF v3 para a vaga X na Ashby") e nunca é a ação padrão do Enter
- [ ] Rejeitar sempre pede motivo (alimenta a calibração da fase 9)
- [ ] Microcopy de apoio embaixo: o que acontece depois ("Volta para a fila de amanhã", "O envio continua em dry-run")
- [ ] Estado de carregando, sucesso (com próximo passo) e erro (com o que fazer)
- [ ] Atalho de teclado nas ações de triagem (aprovar, rejeitar, próxima)
- [ ] `POST` com token CSRF (item F1.8); nunca `GET` que muda estado

## Ações por superfície
| Superfície | Primária | Apoio |
|---|---|---|
| Hoje | Revisar a próxima vaga | Ver motivo da nota, Pular |
| Diff por vaga | Aprovar esta versão | Rejeitar com motivo, Pedir ajuste no chat |
| Candidaturas | Abrir o último evento | Mover de etapa (com motivo) |
| Pendência Gupy | Abrir a vaga na Gupy | Copiar resposta, Baixar PDF |
| Aplicador | Revisar a captura do dry-run | Autorizar submit real (confirmação dupla, só com M4) |
| Email de resumo | Abrir o painel | nenhuma: o email não tem botão que age |

O email de resumo nunca tem link que aprova, envia ou muda estado: só leva ao painel local.

Saída: tabela `local | ação atual | proposta | apoio | por quê`. Para variações, no máximo 3.
