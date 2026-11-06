#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')"
AQUI="$(pwd -P)"
[ "$AQUI" = "$(cd "$ROOT" && pwd -P)" ] && { echo "rode dentro do worktree, nao no checkout principal" >&2; exit 1; }
[ -f "$ROOT/.env" ] || { echo "falta .env no checkout principal" >&2; exit 1; }
[ -x "$ROOT/.venv/bin/python" ] || { echo "falta .venv no checkout principal: rode make setup la" >&2; exit 1; }

EXCLUDE="$(git rev-parse --git-common-dir)/info/exclude"
mkdir -p "$(dirname "$EXCLUDE")"
for nome in .venv .env dados segredos; do
  /usr/bin/grep -qxF "/$nome" "$EXCLUDE" 2>/dev/null || echo "/$nome" >> "$EXCLUDE"
done

for nome in .venv .env dados segredos; do
  [ -e "$ROOT/$nome" ] || continue
  [ -e "$AQUI/$nome" ] || ln -s "$ROOT/$nome" "$AQUI/$nome"
done

git config core.hooksPath .githooks

if docker compose -f "$ROOT/docker-compose.yml" ps --status running postgres 2>/dev/null | /usr/bin/grep -q postgres; then
  echo "banco: pleito-postgres rodando (compartilhado com o checkout principal)"
else
  echo "banco: parado; testes-banco vao falhar ate o Filipe rodar make banco no checkout principal"
fi
echo "worktree pronto: $AQUI"
