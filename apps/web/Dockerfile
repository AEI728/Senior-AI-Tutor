FROM node:22.16.0-slim AS build
RUN npm install -g pnpm@11.25.0
WORKDIR /web
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web .
RUN pnpm build
FROM caddy:2.10.0-alpine
COPY --from=build /web/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
