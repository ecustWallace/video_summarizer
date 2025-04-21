#!/bin/sh

# 使用 envsubst 替换 PORT
envsubst '${PORT}' < /nginx.template.conf > /etc/nginx/conf.d/default.conf

# 启动 nginx
nginx -g 'daemon off;'
