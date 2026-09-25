#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
source .env
set +a

psql_owner() {
    docker compose exec -T \
        -e POSTGRES_APP_PASSWORD="$POSTGRES_APP_PASSWORD" \
        postgres psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
}

psql_owner < db/migrations/0000_controle.sql

aplicadas=0
for arquivo in db/migrations/*.sql db/policies/*.sql; do
    [ "$arquivo" = "db/migrations/0000_controle.sql" ] && continue
    soma=$(shasum -a 256 "$arquivo" | cut -d' ' -f1)
    registrado=$(psql_owner -tAc \
        "SELECT sha256 FROM pleito.migracao WHERE arquivo = '$arquivo'" | tr -d '[:space:]')

    if [ -z "$registrado" ]; then
        echo "aplicando   $arquivo"
        psql_owner < "$arquivo"
        psql_owner -c \
            "INSERT INTO pleito.migracao (arquivo, sha256) VALUES ('$arquivo', '$soma')" >/dev/null
        aplicadas=$((aplicadas + 1))
    elif [ "$registrado" != "$soma" ]; then
        echo "ERRO: $arquivo mudou depois de aplicado" >&2
        echo "  registrado: $registrado" >&2
        echo "  atual:      $soma" >&2
        echo "  crie um arquivo novo em vez de editar um ja aplicado" >&2
        exit 1
    else
        echo "ja aplicado $arquivo"
    fi
done

echo "$aplicadas arquivo(s) aplicado(s) nesta execucao"
