# Brief do implementer (modelo)

O orquestrador preenche e manda como `prompt` do subagente `implementer`. **≤ 40 linhas**, nada de `<placeholder>` sobrando, só fatos conferidos (o que "já existe" tem que existir; na dúvida, escreva "confira").

````text
Item <id> · issue #<N> "<título>" · pleito (lipe0312/pleito)
Worktree: <caminho absoluto> · branch <tipo>/<N>-<slug> (já criada; NÃO troque de branch, NÃO faça git commit/push/stash/reset)
Ambiente: .venv, .env, dados/ e segredos/ são symlinks do checkout principal. Rode tudo de dentro do worktree (`make testes`, `make lint`). Banco: <rodando | parado, não rode testes-banco>. Nunca `make banco`, `make migrar`, `docker compose` nem `make senha-*`.

Fatos que mandam: <seção do docs/PLANO.md e do docs/plano-direcionado.md · ADRs · decisão do Filipe na rodada>.
Critérios de aceite (só eles):
1. <...>
Fora do escopo (vira nota no relatório): <...>
Não toque: <zonas e arquivos das frentes abertas no painel>.

Pré-aprovado: arquivos em <src/x/, config/x.yaml, tests/> · migration: <"nenhuma" | "aditiva em db/migrations/<NNNN>_<nome>.sql, arquivo novo, nunca editar aplicado"> · dependência Python nova: <NÃO | "<pacote>, só se <condição>"> · env nova: <nenhuma | NOME no .env.example, sem valor real>.
Fora disso → pare e devolva BLOQUEIO com opções e recomendação.

Skills a seguir (leia o SKILL.md só quando chegar a hora): <`ui-build` se toca ui · `mkt-copy` se muda texto visível · nenhuma>.
Regras do CLAUDE.md que mais quebram: sem comentário e sem docstring; identificador em português sem acento; nada fixo no código (fonte, limite, horário, termo, domínio, escopo vêm de config/ ou .env); teste ANTES da implementação quando é regra; toda regra de segurança ou de veredito com teste que falha sem ela; nenhuma credencial, email pessoal ou dado do currículo em arquivo versionado, nem em fixture (use dado fictício).
Testes obrigatórios: <regra → teste antes · ataque: <injeção | LaTeX malicioso | remetente forjado | SQL em campo> · banco: teste em tests/test_banco_*.py com marcador do PLEITO_TEST_DATABASE · nenhum teste padrão usa rede>.
Sem rede real e sem LLM real: use respx e o roteador com cliente falso. Egress só dry_run.
Plano: <"siga direto (plano ≤ 15 linhas só para você)" | "PARE depois do plano e devolva só o plano">.
Docs: <marcar o item em docs/plano-direcionado.md (Andamento) · ADR nova em docs/adr/ se houve decisão · docs/banco.md se migration · nenhum>.

Economia: localize com o subagente explorer ou Grep + Read com offset; nunca leia arquivo grande inteiro (docs/PLANO.md só a seção citada). Saídas longas → /tmp/pleito-<N>-*.log e tail. Gate rápido: `.venv/bin/python -m pytest <arquivos> -q && .venv/bin/ruff check <arquivos>`. Ao terminar: `make testes && make lint`. O gate completo e o revisor ficam com o orquestrador.

Devolva EXATAMENTE (≤ 25 linhas):
STATUS: PRONTO | PLANO | BLOQUEIO
O Filipe passa a ver: <1 frase>
Como conferir: <comando ou tela>
Antes → depois: <1–3 bullets>
Toca: Gmail <sim|não> · rede <sim|não> · LLM <sim|não> · migration <arquivo|não> · UI <rota|não>
Arquivos: <lista curta>
Commits sugeridos: "<imperativo, curto, sem código de fase>" + corpo (por quê, o que foi verificado) → <arquivos> (1 a 3 commits)
Testes: <novos e o que cada um prova; quais falham sem a regra>
Docs: <arquivos atualizados | nenhum + motivo>
Casos para o preview: 3 linhas "situação → o que acontece" (comum, borda, ataque ou erro)
Escolhas que fiz sem perguntar: <≤ 3>
Fora do escopo / sugestões de item: <≤ 3>
Manual do Filipe: <OAuth, make banco, plist… | nenhum>
(BLOQUEIO: o que falta + opções + recomendação)
````
