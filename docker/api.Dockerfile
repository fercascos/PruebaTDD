# La API y el worker, en la MISMA imagen.
#
# Son el mismo código y las mismas dependencias; lo único que cambia es el
# comando. Dos imágenes distintas garantizarían que algún día una vaya por
# delante de la otra y que el worker ejecute una versión del generador de
# informes que la API ya no conoce.

ARG BASE=python:3.11-slim-bookworm

# ── Construcción ────────────────────────────────────────────────────────────
FROM ${BASE} AS construccion

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /construccion
COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src

# Un entorno virtual propio, que luego se copia entero. Es la forma más simple
# de dejar en la imagen final exactamente lo instalado y nada más.
#
# `--only-binary=:all:` es deliberado: obliga a que todo venga como rueda
# precompilada. Si algún día una dependencia dejara de publicar rueda para esta
# plataforma, la construcción **falla aquí** en vez de arrastrar en silencio un
# compilador de C a la imagen y tardar diez minutos en cada despliegue.
#
# El secreto `ca_extra` es **opcional** y sirve para redes con inspección TLS,
# que es la norma en muchas empresas: ahí el proxy presenta su propio
# certificado y `pip` —que usa el almacén de `certifi`, no el del sistema—
# rechaza la conexión. Se pasa así, y no como fichero del contexto, para que el
# certificado no quede dentro de ninguna capa de la imagen:
#
#     docker build --secret id=ca_extra,src=/ruta/ca-corporativa.crt ...
#
# Sin el secreto, la línea no hace nada.
RUN --mount=type=secret,id=ca_extra \
    set -eu; \
    if [ -s /run/secrets/ca_extra ]; then \
      cp /run/secrets/ca_extra /usr/local/share/ca-certificates/corporativa.crt; \
      update-ca-certificates; \
      export PIP_CERT=/etc/ssl/certs/ca-certificates.crt; \
      echo "Certificado corporativo instalado para la construcción."; \
    fi; \
    python -m venv /opt/venv; \
    /opt/venv/bin/pip install --upgrade pip; \
    /opt/venv/bin/pip install --only-binary=:all: .

# ── Ejecución ───────────────────────────────────────────────────────────────
FROM ${BASE} AS ejecucion

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# `fc-match` es lo que usa `reporting/fonts.py` para medir el texto de las
# diapositivas con la tipografía REAL. Sin él, el aviso de desbordamiento sería
# un número inventado, así que el módulo prefiere callarse: la imagen sin
# fontconfig funciona, pero pierde una función del bloque 4.
#
# Se instala **solo si la base no lo trae** —las imágenes `python:3.11-bookworm`
# completas ya incluyen fontconfig, las `slim` no—, para que la misma receta
# valga con cualquier base y no se pague una descarga de paquetes cuando no
# hace falta.
RUN if ! command -v fc-match >/dev/null 2>&1; then \
      apt-get update \
      && apt-get install --no-install-recommends -y fontconfig \
      && rm -rf /var/lib/apt/lists/*; \
    fi \
 && fc-match --version

# `[LIM]` Las tipografías corporativas (Gotham) **no van en la imagen**. Son
# comerciales, el repositorio tiene una comprobación (`make no-fonts`) que
# impide versionarlas, y meterlas aquí las distribuiría con cada copia de la
# imagen. Se montan en `/usr/share/fonts/corporativas` al desplegar.
RUN mkdir -p /usr/share/fonts/corporativas

# Sin privilegios. Que la aplicación no pueda escribir en su propio código es
# una barrera barata y real.
RUN useradd --create-home --uid 10001 tdd
COPY --from=construccion /opt/venv /opt/venv

# La disposición de dentro **es la del repositorio**, y no una más plana, a
# propósito: hay módulos que localizan ficheros contando directorios hacia
# arriba —`catalogs/seeding.py` busca `data/catalogos/*.csv` cinco niveles por
# encima de sí mismo—. Aplanar la estructura dejaría esa ruta apuntando a la
# raíz del sistema de ficheros y la siembra fallaría solo dentro del
# contenedor, que es el peor sitio donde descubrirlo.
COPY --chown=tdd:tdd apps/api/alembic.ini /app/apps/api/alembic.ini
COPY --chown=tdd:tdd apps/api/src /app/apps/api/src
COPY --chown=tdd:tdd data /app/data

# El almacén sobre disco escribe aquí cuando `STORAGE_BACKEND=disco`. En un
# despliegue de verdad esto es un volumen, o mejor `STORAGE_BACKEND=s3`.
RUN mkdir -p /var/tdd/objetos && chown -R tdd:tdd /var/tdd

WORKDIR /app
USER tdd
ENV PYTHONPATH=/app/apps/api/src \
    STORAGE_LOCAL_DIR=/var/tdd/objetos

EXPOSE 8000

# La sonda va con Python, que ya está aquí, en vez de con `curl`: una
# herramienta menos que instalar y una menos en la superficie de ataque.
#
# Comprueba el proceso, no la base. Si PostgreSQL se cae, el contenedor de la
# API no está roto y reiniciarlo no arregla nada; lo que esto responde es
# «¿sigue este proceso atendiendo?».
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "tdd.main:app", "--host", "0.0.0.0", "--port", "8000"]
