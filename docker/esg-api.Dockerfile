# La API del dashboard ESG.
#
# Mucho más simple que la de la due diligence, y es a propósito: aquí no hay
# tipografías corporativas, ni almacén de objetos, ni generación de PPTX. Lo que
# sí comparte es lo que importa —rueda precompilada obligatoria, secreto para la
# CA corporativa, usuario sin privilegios— porque esas tres cosas se aprendieron
# pagándolas.

ARG BASE=python:3.11-slim-bookworm

FROM ${BASE} AS construccion

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /construccion
COPY apps/esg-api/pyproject.toml ./
COPY apps/esg-api/src ./src

# `--only-binary=:all:`: si una dependencia deja de publicar rueda para esta
# plataforma, la construcción falla AQUÍ, en vez de arrastrar en silencio un
# compilador de C a la imagen.
#
# El secreto `ca_extra` es opcional, para redes con inspección TLS. Se pasa como
# secreto y no como fichero del contexto para que el certificado no quede en
# ninguna capa:  docker build --secret id=ca_extra,src=/ruta/ca.crt ...
RUN --mount=type=secret,id=ca_extra \
    set -eu; \
    if [ -s /run/secrets/ca_extra ]; then \
      cp /run/secrets/ca_extra /usr/local/share/ca-certificates/corporativa.crt; \
      update-ca-certificates; \
      export PIP_CERT=/etc/ssl/certs/ca-certificates.crt; \
    fi; \
    python -m venv /opt/venv; \
    /opt/venv/bin/pip install --upgrade pip; \
    /opt/venv/bin/pip install --only-binary=:all: .

FROM ${BASE} AS ejecucion

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Sin privilegios: que la aplicación no pueda escribir en su propio código es
# una barrera barata y real.
RUN useradd --create-home --uid 10002 esg
COPY --from=construccion /opt/venv /opt/venv
COPY --chown=esg:esg apps/esg-api/src /app/apps/esg-api/src

WORKDIR /app
USER esg
ENV PYTHONPATH=/app/apps/esg-api/src

EXPOSE 8000

# Con Python, que ya está, en vez de con curl: una herramienta menos que
# instalar y una menos en la superficie de ataque. Comprueba el proceso, no la
# base: si PostgreSQL se cae, reiniciar este contenedor no arregla nada.
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "esg.main:app", "--host", "0.0.0.0", "--port", "8000"]
