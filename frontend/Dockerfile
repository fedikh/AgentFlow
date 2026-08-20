# ── AgentFlow frontend (Vite build → served by nginx) ──

# Stage 1: build the static site. VITE_* vars are baked in at build time;
# they come from frontend/.env (API URL + Google keys) — see .env.
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve the built /dist with nginx (SPA routing fallback)
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
