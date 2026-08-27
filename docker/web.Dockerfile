# El frontend: se construye con Node y se sirve con nginx.
#
# La imagen final no lleva Node ni `node_modules`: lo que se publica son unos
# cuantos ficheros estáticos. nginx además hace de proxy de `/api`, con lo que
# navegador y API comparten origen y no hay CORS que configurar —que es
# exactamente lo que `vite.config.ts` ya hace en desarrollo—.

# ── Construcción ────────────────────────────────────────────────────────────
FROM node:22-bookworm-slim AS construccion

WORKDIR /construccion
COPY apps/web/package.json apps/web/package-lock.json* ./

# `npm ci` si hay fichero de bloqueo —reproducible— y `npm install` si no. El
# navegador no perdona una dependencia que cambió sola entre dos despliegues.
#
# `ca_extra` es el mismo secreto opcional que en `api.Dockerfile`, para redes
# con inspección TLS. Node no lee el almacén del sistema: se le indica el
# fichero con `NODE_EXTRA_CA_CERTS`. Sin el secreto, no hace nada.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN --mount=type=secret,id=ca_extra \
    set -eu; \
    if [ -s /run/secrets/ca_extra ]; then \
      mkdir -p /usr/local/share/ca-certificates; \
      cp /run/secrets/ca_extra /usr/local/share/ca-certificates/corporativa.crt; \
      # A Node se le pasa el fichero directamente: `NODE_EXTRA_CA_CERTS` SUMA
      # a las raíces que ya trae, así que no hace falta reconstruir el almacén
      # del sistema —que en las imágenes `slim` puede ni existir—.
      export NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/corporativa.crt; \
      echo "Certificado corporativo instalado para la construcción."; \
    fi; \
    if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY apps/web ./
RUN npm run build

# ── Ejecución ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS ejecucion

# A `templates/`, no a `conf.d/`: la imagen de nginx sustituye las variables de
# entorno de los ficheros de `templates/` al arrancar y deja el resultado en
# `conf.d/`. Así el mismo fichero sirve para compose y para otro despliegue.
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=construccion /construccion/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost/index.html || exit 1
