FROM node:22-alpine AS build
WORKDIR /app/web
# the API the /api/* proxy points at is fixed at build time
ARG DL_API_URL=http://localhost:8000
ENV DL_API_URL=$DL_API_URL NEXT_TELEMETRY_DISABLED=1
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
COPY src/decision_layer/i18n/ko.json /app/src/decision_layer/i18n/ko.json
RUN npm run build

FROM node:22-alpine
WORKDIR /app/web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app /app
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000", "-H", "0.0.0.0"]
