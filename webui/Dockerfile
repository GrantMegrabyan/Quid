# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# No build-time API URL: PUBLIC_API_BASE_URL is read at runtime via
# $env/dynamic/public, so the image is environment-agnostic.
RUN npm run build

# Production stage
FROM node:22-alpine

RUN addgroup -S app && adduser -S app -G app

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/build ./build

RUN chown -R app:app /app
USER app

EXPOSE 3000

ENV HOST=0.0.0.0
ENV PORT=3000

# PUBLIC_API_BASE_URL is supplied at runtime (docker-compose `environment:`).
CMD ["node", "build"]
