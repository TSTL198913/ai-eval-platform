# =====================================================================
# Frontend Dockerfile - AI Eval Platform
# 构建并服务React前端
# =====================================================================

FROM node:20-alpine AS builder

WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# =====================================================================
# 生产镜像 - 使用Nginx服务静态文件
# =====================================================================
FROM nginx:alpine AS production

# 安装curl用于健康检查
RUN apk add --no-cache curl

# 删除默认nginx配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制自定义nginx配置
COPY docker/nginx.conf /etc/nginx/conf.d/

# 从builder阶段复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]
