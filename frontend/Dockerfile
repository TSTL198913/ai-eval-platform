FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY frontend/ ./frontend/
COPY vite.config.ts ./
COPY tsconfig.json ./

RUN npm run build

FROM nginx:alpine AS production

RUN apk add --no-cache curl

RUN rm /etc/nginx/conf.d/default.conf

COPY frontend/nginx.conf /etc/nginx/conf.d/

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
