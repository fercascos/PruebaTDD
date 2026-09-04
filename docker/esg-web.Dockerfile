# La interfaz del ESG: se construye con Node y se sirve con nginx.
#
# Las variables `VITE_*` se resuelven **al construir**, no al arrancar: son
# parte del JavaScript que se descarga el navegador. Por eso van como `ARG` y
# no como entorno del contenedor, donde no harían nada y se tardaría media
# tarde en entender por qué.

FROM node:22-alpine AS construccion
WORKDIR /construccion
COPY apps/esg-web/package.json apps/esg-web/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY apps/esg-web/ ./
ARG VITE_API_URL=""
ARG VITE_AUTH_MODE=local
ARG VITE_AZURE_CLIENT_ID=""
ARG VITE_AZURE_TENANT_ID=""
ARG VITE_AZURE_SCOPE=""
ENV VITE_API_URL=$VITE_API_URL \
    VITE_AUTH_MODE=$VITE_AUTH_MODE \
    VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID \
    VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID \
    VITE_AZURE_SCOPE=$VITE_AZURE_SCOPE
RUN npm run build

FROM nginx:1.27-alpine AS ejecucion
COPY docker/esg-web.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=construccion /construccion/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=4s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null || exit 1
