# =====================================================================
# AI Evaluation Platform - Frontend Dockerfile
# =====================================================================

FROM node:20-alpine AS builder

WORKDIR /app

# 复制前端目录内容到 /app（而不是 /app/frontend）
COPY frontend/package*.json ./
COPY frontend/vite.config.ts ./
COPY frontend/tsconfig.json ./
COPY frontend/src ./src
COPY frontend/index.html ./
COPY frontend/nginx.conf ./
COPY public ./public

# 安装依赖并构建
RUN npm ci && npm run build

FROM nginx:alpine AS production

RUN apk add --no-cache curl

RUN rm /etc/nginx/conf.d/default.conf

COPY frontend/nginx.conf /etc/nginx/conf.d/

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
