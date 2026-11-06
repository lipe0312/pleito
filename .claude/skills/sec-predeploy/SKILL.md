---
name: sec-predeploy
description: Portão de segurança do pleito em três níveis — por PR que toca credencial, Gmail, egress, LLM, LaTeX ou banco; antes de ligar algo de verdade (sistema_ativo, habilitar tier, primeira rotina agendada, submit real); e auditoria completa com a skill security-audit (Cloudflare) por trimestre. Só reporta; correções viram itens do backlog. Use antes de ligar qualquer coisa real ou depois de mudar segurança.
---

# Segurança antes de ligar

O pleito não tem deploy: "ligar" é virar a flag `sistema_ativo`, pôr `habilitado: true` num tier, instalar o plist do launchd (M3) ou autorizar um submit real (M4). Esta skill **não corrige nada sozinha**: gera relatório → o Filipe prioriza → itens do backlog (`groom-issue`). Referência dos controles: `docs/seguranca.md` e `docs/ameacas.md`.

## Nível 1 · todo PR que toca credencial, terceiro, banco, llm, latex ou seguranca (barato)
- Subagente `guarda-seguranca` no diff (a `next-task-full` já chama).
- `/security-review` (comando nativo) na branch quando o diff toca `src/email/`, `src/llm/`, `src/aplicador/`, `src/painel/`, `db/policies/` ou `.githooks/`.

## Nível 2 · antes de ligar algo real (médio)
Confira no código e no ambiente, com `arquivo:linha` ou comando:
- [ ] `git ls-files | /usr/bin/grep -E '^(dados|segredos)/|^\.env$'` vazio; `.env` e `segredos/*` com `chmod 600` (`stat -f '%Lp' .env`)
- [ ] `.env.example` sem valor real; nenhum email pessoal, telefone ou token em arquivo versionado (`git grep -nE '@gmail\.com|sk-[A-Za-z0-9]{20}|gh[pousr]_[A-Za-z0-9]{20}'`)
- [ ] Refresh token só no Keychain (serviço de `config/emails.yaml`); nada de token em `dados/` (`/usr/bin/find dados -name '*token*'` vazio)
- [ ] Escopos OAuth em `config/emails.yaml` são o mínimo (`gmail.modify`; envio só no módulo de resumo, destino de `PLEITO_EMAIL_DESTINO`)
- [ ] Teste de arquitetura de email verde (sem delete, trash, forward ou send fora do resumo)
- [ ] Painel e banco ligados só em `127.0.0.1` (`docker-compose.yml`, `src/painel/__main__.py`); Host, CSP e CSRF do painel (item F1.8)
- [ ] `PLEITO_EGRESS_MODO` = `dry_run` fora de uma execução autorizada; o token de submit não está no `.env` fora dela
- [ ] Tier com `habilitado: true` tem `avaliacao.status`, `conjunto` e `data` preenchidos (ADR 0017); cache de prompt desligado (ADR 0019)
- [ ] Orçamento: `config/limites.yaml` igual ao limite do projeto na OpenAI (manual M7)
- [ ] Papéis do banco: grants por coluna e auditoria só INSERT (`make testes-banco` verde)
- [ ] Dependências: `gh api repos/lipe0312/pleito --jq .security_and_analysis` mostra `dependabot_security_updates` e `secret_scanning` ativos (F0.3); `.github/dependabot.yml` tem só pip, weekly e `open-pull-requests-limit`; com F0.2 feito, `make auditoria` sem vulnerabilidade alta nova
- [ ] `main` protegida (F0.4): `gh api repos/lipe0312/pleito/branches/main/protection --jq .allow_force_pushes.enabled` = `false`

## Nível 3 · por trimestre e antes do primeiro submit real (caro: peça aprovação)
Skill **security-audit** (cloudflare/security-audit-skill, em `.claude/skills/security-audit`): recon → hunting → validação → relatório → verificação independente. Escopo: `src/email/`, `src/llm/`, `src/painel/`, `src/coletor/`, `src/aplicador/`, `src/db/`, `db/policies/`, `scripts/`, `.githooks/`. Classes que mais importam aqui: injeção de prompt e saída de LLM (`AI-AND-LLM.md`), SSRF e allowlist da coleta, segredo em disco e em log, IPC local e loopback do OAuth (`DESKTOP-MOBILE-AND-LOCAL-IPC.md`), cadeia de suprimentos (`SUPPLY-CHAIN-AND-RELEASE.md`). Rode só contra o código local; **nunca** contra a conta Gmail, a OpenAI ou uma plataforma de vaga.

## Saída
Tabela: severidade · `arquivo:linha` · cenário de exploração · correção sugerida · item proposto (id e zona). Só achados confirmados; "precisa validar" em seção separada. Nunca cole segredo, token ou dado pessoal no relatório.
