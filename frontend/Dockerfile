# 构建阶段
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN export http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= all_proxy= no_proxy='*' NO_PROXY='*'; \
    npm install --registry https://registry.npmmirror.com
COPY . .
RUN export http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= all_proxy= no_proxy='*' NO_PROXY='*'; \
    npm run build

# 运行阶段：nginx 托管静态资源 + 反向代理 /api 到后端
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
