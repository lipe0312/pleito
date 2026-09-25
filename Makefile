SHELL := /bin/bash
PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup banco banco-baixo migrar psql testes lint viabilidade limpar

setup:
	/opt/homebrew/bin/python3.11 -m venv .venv || python3.11 -m venv .venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"
	$(PY) -m playwright install chromium

banco:
	docker compose up -d
	@echo "postgres  -> 127.0.0.1:$${POSTGRES_PORT:-55432}"
	@echo "pgadmin   -> http://127.0.0.1:$${PGADMIN_PORT:-55050}"

banco-baixo:
	docker compose down

migrar:
	@set -a && source .env && set +a && \
	for f in db/migrations/*.sql db/policies/*.sql; do \
	  echo "aplicando $$f"; \
	  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" < "$$f"; \
	done

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
