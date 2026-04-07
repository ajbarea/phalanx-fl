# syntax=docker/dockerfile:1.7

# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

# Dependencies first for layer caching with cache mount
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --silent

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

LABEL org.opencontainers.image.title="IntelliFL" \
      org.opencontainers.image.description="Web UI for federated learning simulations" \
      org.opencontainers.image.source="https://github.com/dmitrykoro/fl-execution-framework" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.documentation="https://intellifl.readthedocs.io" \
      org.opencontainers.image.vendor="IntelliFL Contributors" \
      com.docker.scout.disable="false"

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/
COPY --from=builder /app/dist /usr/share/nginx/html

# Run as non-root for security
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
