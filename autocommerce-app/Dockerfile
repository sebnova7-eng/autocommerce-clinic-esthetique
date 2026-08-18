FROM node:22-alpine AS builder

ARG PNPM_VERSION=10.15.1
RUN npm install -g pnpm@${PNPM_VERSION}

WORKDIR /workspace
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

# Build from the monorepo root so pnpm overrides and patched dependencies match the lockfile.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY autocommerce-app/package.json ./autocommerce-app/package.json
COPY autocommerce-app/patches ./autocommerce-app/patches
RUN pnpm install --frozen-lockfile

COPY autocommerce-app ./autocommerce-app
RUN pnpm --filter autocommerce-clinic-frontend build

FROM nginx:alpine
COPY --from=builder /workspace/autocommerce-app/dist/public /usr/share/nginx/html

COPY autocommerce-app/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD wget --quiet --tries=1 --spider http://127.0.0.1/index.html || exit 1
CMD ["nginx", "-g", "daemon off;"]
