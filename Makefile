SHELL := /bin/bash
PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup banco banco-status banco-baixo pgadmin-container migrar psql testes lint viabilidade limpar

setup:
	/opt/homebrew/bin/python3.11 -m venv .venv || python3.11 -m venv .venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"
	$(PY) -m playwright install chromium

banco:
	docker compose up -d postgres
	@set -a && source .env && set +a && \
	echo "postgres do pleito -> 127.0.0.1:$$POSTGRES_PORT (cluster proprio, isolado do 5432)"

banco-status:
	@docker compose ps postgres
	@set -a && source .env && set +a && \
	docker compose exec -T postgres psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" \
	  -c "select current_database(), current_user, version();"

pgadmin-container:
	docker compose --profile pgadmin-container up -d pgadmin
	@set -a && source .env && set +a && echo "pgadmin -> http://127.0.0.1:$$PGADMIN_PORT"

banco-baixo:
	docker compose down

migrar:
	./scripts/migrar.sh

psql:
	@set -a && source .env && set +a && \
	docker compose exec -it postgres psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"

testes:
	$(PY) -m pytest -m "not rede and not navegador and not latex"

testes-todos:
	$(PY) -m pytest

lint:
	.venv/bin/ruff check .

viabilidade:
	$(PY) -m viabilidade.cli veredito

limpar:
	rm -rf .pytest_cache .ruff_cache **/__pycache__
