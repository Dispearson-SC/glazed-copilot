# Production web: build the PWA with same-origin API calls, serve it with nginx.
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_DEFAULT_SIM_TODAY=""
ENV VITE_API_URL="" VITE_DEFAULT_SIM_TODAY=$VITE_DEFAULT_SIM_TODAY
RUN npm run build

FROM nginx:1.27-alpine
COPY infra/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
