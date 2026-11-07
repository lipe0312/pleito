SHELL := /bin/bash
PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup banco banco-status banco-baixo pgadmin-container migrar psql senha-banco senha-app senha-rotacionar testes testes-banco auditoria painel painel-ficticio lint viabilidade limpar gmail-autorizar conteudo gmail-organizar resumo conteudo-sincronizar conteudo-aprovar avaliar

setup:
	/opt/homebrew/bin/python3.11 -m venv .venv || python3.11 -m venv .venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"
	git config core.hooksPath .githooks
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

senha-banco:
	@set -a && source .env && set +a && \
	printf '%s' "$$POSTGRES_PASSWORD" | pbcopy && \
	echo "POSTGRES_PASSWORD copiada ($${#POSTGRES_PASSWORD} chars). Cole no pgAdmin com Cmd+V."

senha-app:
	@set -a && source .env && set +a && \
	printf '%s' "$$POSTGRES_APP_PASSWORD" | pbcopy && \
	echo "POSTGRES_APP_PASSWORD copiada ($${#POSTGRES_APP_PASSWORD} chars)."

senha-rotacionar:
	./scripts/rotacionar-senha.sh

testes:
	$(PY) -m pytest -m "not rede and not navegador and not latex"

testes-banco:
	PLEITO_TEST_DATABASE=1 $(PY) -m pytest tests/test_banco_permissoes.py tests/test_banco_vagas.py tests/test_banco_eventos_email.py

testes-todos:
	$(PY) -m pytest

painel:
	$(PY) -m src.painel

painel-ficticio:
	$(PY) -m src.painel --ficticio tests/fixtures/painel_ficticio.yaml

lint:
	.venv/bin/ruff check .

auditoria:
	$(PY) -m pip_audit

gmail-autorizar:
	$(PY) scripts/autorizar_gmail.py

conteudo:
	$(PY) -m src.conteudo

conteudo-sincronizar:
	$(PY) -m src.conteudo.sincronizar

conteudo-aprovar:
	$(PY) -m src.conteudo.aprovar $(ARGS)

gmail-organizar:
	$(PY) scripts/organizar_gmail.py $(ARGS)

resumo:
	$(PY) -m src.email.resumo $(ARGS)

agendamento-plist:
	$(PY) -m src.agendamento.plist $(ARGS)

avaliar:
	@test -n "$(TIER)" || (echo "use: make avaliar TIER=forte [ARGS=--real]" && exit 2)
	$(PY) -m src.avaliacao --tier $(TIER) $(ARGS)

viabilidade:
	$(PY) -m viabilidade.cli veredito

limpar:
	rm -rf .pytest_cache .ruff_cache **/__pycache__
