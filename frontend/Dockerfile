# ⚙️ 构建阶段
FROM node:18-alpine AS builder

WORKDIR /app
COPY . .
RUN npm install
RUN npm run build

# ⚙️ 生产阶段
FROM nginx:stable-alpine as production

# 拷贝构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 拷贝模板和启动脚本
COPY nginx.template.conf /nginx.template.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 告诉 Cloud Run 我们监听 8080
ENV PORT 8080
EXPOSE 8080

CMD ["/entrypoint.sh"]
