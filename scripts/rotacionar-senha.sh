#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

alvo="${1:-owner}"
case "$alvo" in
    owner) chave=POSTGRES_PASSWORD ;;
    app)   chave=POSTGRES_APP_PASSWORD ;;
    *)     echo "uso: $0 [owner|app]" >&2; exit 2 ;;
esac

set -a
source .env
set +a

if [ "$alvo" = "owner" ]; then
    role="$POSTGRES_USER"
else
    role="pleito_app_login"
fi

nova=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

python3 - "$role" "$nova" <<'PY' | docker compose exec -T postgres \
    psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
import re
import sys

role, senha = sys.argv[1], sys.argv[2]
if not re.fullmatch(r"[A-Za-z0-9_]+", role):
    raise SystemExit(f"nome de role inesperado: {role!r}")
if not re.fullmatch(r"[A-Za-z0-9_-]+", senha):
    raise SystemExit("senha gerada tem caractere inesperado")
print(f"ALTER ROLE \"{role}\" WITH PASSWORD '{senha}';")
PY

python3 - "$chave" "$nova" <<'PY'
import re
import sys
from pathlib import Path

chave, nova = sys.argv[1], sys.argv[2]
p = Path(".env")
t = p.read_text()
t, n = re.subn(rf"^{chave}=.*$", f"{chave}={nova}", t, flags=re.MULTILINE)
if n != 1:
    raise SystemExit(f"esperava 1 linha {chave} no .env, achei {n}")
p.write_text(t)
PY

chmod 600 .env
printf '%s' "$nova" | pbcopy
echo "$chave rotacionada para $role (${#nova} chars)"
echo ".env atualizado, senha nova na area de transferencia"
echo "atualize a senha salva no pgAdmin, e o ~/.pgpass se voce usa"
