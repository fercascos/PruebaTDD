.DEFAULT_GOAL := help
SHELL := /bin/bash

PG_BIN  ?= /usr/lib/postgresql/16/bin
PGDATA  ?= /var/lib/postgresql/16/tdd
PGPORT  ?= 55432
PGSOCK  ?= /tmp
DB      ?= tdd
# [REQ] La suite corre sobre una base APARTE. Su `conftest` hace un
# `DROP SCHEMA public CASCADE` en cada arranque: apuntándola a `tdd` bastaba con
# ejecutar `make test` una vez para perder los datos de desarrollo, el
# administrador incluido, y volver a una aplicación en la que no se puede
# entrar. Se descubrió justo así.
TEST_DB ?= tdd_test
APP_ROLE ?= tdd_app
# [REQ] Solo para la base local de desarrollo. No es un secreto de producción:
# fuera de local la contraseña viene del entorno y no está en ningún fichero.
APP_PASS ?= prueba-local-sin-valor-real

# Conexión de ADMINISTRACIÓN a la base de DESARROLLO: crea el esquema y siembra.
# Es superusuario, así que la RLS **no se le aplica**; por eso no la usa nunca
# la aplicación.
ADMIN_DATABASE_URL ?= postgresql+psycopg://postgres@/$(DB)?host=$(PGSOCK)&port=$(PGPORT)
# La de la SUITE. Otra base: ver el comentario de TEST_DB.
TEST_DATABASE_URL ?= postgresql+psycopg://postgres@/$(TEST_DB)?host=$(PGSOCK)&port=$(PGPORT)
# Conexión de la APLICACIÓN. `tdd_app` no es propietario ni tiene BYPASSRLS:
# arrancar la API con la de administración dejaría la RLS sin efecto y todo
# parecería funcionar, que es la peor forma de que falle.
#
# Va por TCP y no por el socket de Unix a propósito: `DATABASE_URL` la valida
# `PostgresDsn`, y la forma `@/base?host=...` que usan las órdenes de psql no
# lleva anfitrión, así que Pydantic la rechaza al arrancar.
PGHOST_TCP ?= localhost
APP_DATABASE_URL ?= postgresql+psycopg://$(APP_ROLE):$(APP_PASS)@$(PGHOST_TCP):$(PGPORT)/$(DB)

help:  ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Instala las dependencias del backend
	pip install -e "apps/api[dev]"

db-up:  ## Arranca PostgreSQL local
	@su postgres -c "PATH=$(PG_BIN):\$$PATH pg_ctl -D $(PGDATA) -o '-p $(PGPORT) -k $(PGSOCK)' -l $(PGDATA)/../log start" || true
	@sleep 2 && psql -h $(PGSOCK) -p $(PGPORT) -U postgres -tAc 'select version()'

db-init:  ## Crea las bases y aplica el esquema (DESTRUCTIVO: las recrea)
	psql -h $(PGSOCK) -p $(PGPORT) -U postgres -q \
	  -c "DROP DATABASE IF EXISTS $(DB);" -c "CREATE DATABASE $(DB);" \
	  -c "DROP DATABASE IF EXISTS $(TEST_DB);" -c "CREATE DATABASE $(TEST_DB);"
	@$(MAKE) --no-print-directory db-migrate
	psql -h $(PGSOCK) -p $(PGPORT) -U postgres -q -d $(DB) -v ON_ERROR_STOP=1 \
	  -c "DROP ROLE IF EXISTS $(APP_ROLE);" \
	  -c "CREATE ROLE $(APP_ROLE) LOGIN PASSWORD '$(APP_PASS)';"
	@$(MAKE) --no-print-directory db-grant
	@$(MAKE) --no-print-directory db-seed
	@echo "Base $(DB) lista. El rol $(APP_ROLE) NO tiene BYPASSRLS: es lo que hace que la RLS sirva."
	@echo "Siguiente paso: make db-admin ORG='...' EMAIL='...' NOMBRE='...'"

db-migrate:  ## Aplica las migraciones pendientes (alembic upgrade head)
	@cd apps/api && PYTHONPATH=src DATABASE_MIGRATION_URL="$(ADMIN_DATABASE_URL)" \
	  python3 -m alembic upgrade head
	@$(MAKE) --no-print-directory db-grant

# Una migración que crea una tabla la crea como `postgres`, y `tdd_app` —que no
# es propietario— se queda sin permisos sobre ella: la tabla existe, la RLS está
# puesta y la aplicación recibe «permission denied» en cuanto la toca. Por eso
# los permisos se vuelven a dar después de CADA migración, no solo al crear la
# base. Es idempotente y no cuesta nada.
db-grant:  ## Da al rol de aplicación permisos sobre lo que exista ahora
	@psql -h $(PGSOCK) -p $(PGPORT) -U postgres -q -d $(DB) -v ON_ERROR_STOP=1 \
	  -c "GRANT USAGE ON SCHEMA public TO $(APP_ROLE);" \
	  -c "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $(APP_ROLE);" \
	  -c "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $(APP_ROLE);"

db-revision:  ## Crea una migración vacía: make db-revision M="lo que cambia"
	@cd apps/api && PYTHONPATH=src DATABASE_MIGRATION_URL="$(ADMIN_DATABASE_URL)" \
	  python3 -m alembic revision -m "$(M)"
	@echo
	@echo "Recuerde: actualice también apps/api/src/tdd/db/schema.sql."
	@echo "Es la verdad del esquema, y test_migraciones.py falla si divergen."

db-sql:  ## Imprime el SQL de las migraciones pendientes sin ejecutarlo
	@cd apps/api && PYTHONPATH=src DATABASE_MIGRATION_URL="$(ADMIN_DATABASE_URL)" \
	  python3 -m alembic upgrade head --sql

db-version:  ## Qué versión del esquema tiene la base
	@cd apps/api && PYTHONPATH=src DATABASE_MIGRATION_URL="$(ADMIN_DATABASE_URL)" \
	  python3 -m alembic current

db-seed:  ## Siembra catálogos y fases en la base de desarrollo (idempotente)
	@cd apps/api && PYTHONPATH=src DATABASE_URL="$(ADMIN_DATABASE_URL)" python3 -m tdd.db.sembrar

db-admin:  ## Crea la primera organización y su administrador (pide la clave)
	@cd apps/api && PYTHONPATH=src DATABASE_URL="$(ADMIN_DATABASE_URL)" python3 -m tdd.db.arranque \
	  --org "$(ORG)" --email "$(EMAIL)" --nombre "$(NOMBRE)"

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

run:  ## Arranca la API en local (como tdd_app: con la RLS en vigor)
	cd apps/api && PYTHONPATH=src DATABASE_URL="$(APP_DATABASE_URL)" \
	  python3 -m uvicorn tdd.main:app --reload --port 8000

ci: catalogs-check no-fonts lint test  ## Lo que debe pasar antes de un push

.PHONY: help install db-up db-init db-migrate db-revision db-sql db-version db-seed db-admin catalogs catalogs-check test test-unit test-rls \
        test-catalogs lint fmt no-fonts run ci
