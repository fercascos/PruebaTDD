.DEFAULT_GOAL := help
SHELL := /bin/bash

PG_BIN  ?= /usr/lib/postgresql/16/bin
PGDATA  ?= /var/lib/postgresql/16/tdd
PGPORT  ?= 55432
PGSOCK  ?= /tmp
DB      ?= tdd
TEST_DATABASE_URL ?= postgresql+psycopg://postgres@/$(DB)?host=$(PGSOCK)&port=$(PGPORT)

help:  ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Instala las dependencias del backend
	pip install -e "apps/api[dev]"

db-up:  ## Arranca PostgreSQL local
	@su postgres -c "PATH=$(PG_BIN):\$$PATH pg_ctl -D $(PGDATA) -o '-p $(PGPORT) -k $(PGSOCK)' -l $(PGDATA)/../log start" || true
	@sleep 2 && psql -h $(PGSOCK) -p $(PGPORT) -U postgres -tAc 'select version()'

db-init:  ## Crea la base y aplica el esquema (DESTRUCTIVO: la recrea)
	psql -h $(PGSOCK) -p $(PGPORT) -U postgres -q \
	  -c "DROP DATABASE IF EXISTS $(DB);" -c "CREATE DATABASE $(DB);"
	psql -h $(PGSOCK) -p $(PGPORT) -U postgres -q -d $(DB) -v ON_ERROR_STOP=1 \
	  -f apps/api/src/tdd/db/schema.sql
	psql -h $(PGSOCK) -p $(PGPORT) -U postgres -q -d $(DB) \
	  -c "DROP ROLE IF EXISTS tdd_app;" \
	  -c "CREATE ROLE tdd_app LOGIN PASSWORD 'prueba-local-sin-valor-real';"
	@echo "Base $(DB) lista. El rol tdd_app NO tiene BYPASSRLS: es lo que hace que la RLS sirva."

catalogs:  ## Regenera los CSV de catálogos desde docs/05
	python3 tools/generar_catalogos.py

catalogs-check:  ## Falla si los CSV están desfasados respecto del documento
	python3 tools/generar_catalogos.py --check

test:  ## Suite completa (necesita PostgreSQL en marcha)
	cd apps/api && TEST_DATABASE_URL="$(TEST_DATABASE_URL)" python3 -m pytest -q

test-unit:  ## Solo unitarias: no necesitan base de datos
	cd apps/api && python3 -m pytest tests/unit -q

test-rls:  ## Solo el aislamiento por Row Level Security
	cd apps/api && TEST_DATABASE_URL="$(TEST_DATABASE_URL)" \
	  python3 -m pytest tests/integration/test_rls_y_restricciones.py -q

test-catalogs:  ## Las 86 combinaciones zona × tipología y el árbol
	cd apps/api && TEST_DATABASE_URL="$(TEST_DATABASE_URL)" \
	  python3 -m pytest tests/integration/test_catalogos.py -q

lint:  ## ruff + mypy
	cd apps/api && python3 -m ruff check src tests && python3 -m ruff format --check src tests

fmt:  ## Formatea
	cd apps/api && python3 -m ruff format src tests && python3 -m ruff check --fix src tests

no-fonts:  ## Falla si hay tipografías versionadas (Gotham es licenciada)
	@if git ls-files | grep -qiE '\.(otf|ttf|woff2?)$$'; then \
	  echo "ERROR: hay tipografías versionadas. Gotham es comercial: no va al repositorio."; \
	  git ls-files | grep -iE '\.(otf|ttf|woff2?)$$'; exit 1; \
	else echo "Sin tipografías versionadas."; fi

run:  ## Arranca la API en local
	cd apps/api && DATABASE_URL="$(TEST_DATABASE_URL)" \
	  python3 -m uvicorn tdd.main:app --reload --port 8000

ci: catalogs-check no-fonts lint test  ## Lo que debe pasar antes de un push

.PHONY: help install db-up db-init catalogs catalogs-check test test-unit test-rls \
        test-catalogs lint fmt no-fonts run ci
