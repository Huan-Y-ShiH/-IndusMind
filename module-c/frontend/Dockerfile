FROM node:22-alpine AS build

WORKDIR /app

# Install pnpm v9 (lockfile v6)
RUN corepack enable && corepack prepare pnpm@9 --activate

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --no-frozen-lockfile

COPY . .
RUN pnpm build

# ── Production nginx stage ─────────────────────────────────────────

FROM nginx:1.25-alpine

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
