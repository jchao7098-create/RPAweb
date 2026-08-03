# RPA 项目管理系统 —— 前端镜像（两阶段：node 构建 → nginx 托管静态产物）

# ---------- 阶段一：构建 ----------
# 基础镜像走 DaoCloud 加速，国内直连不超时
FROM docker.m.daocloud.io/library/node:20-alpine AS build

WORKDIR /app

# 先装依赖再拷代码，改代码不重装依赖（利用构建缓存）
COPY package.json package-lock.json ./

# 内网/国内服务器拉 npm 慢或超时，直接用 npmmirror 镜像
RUN npm config set registry https://registry.npmmirror.com && npm ci

COPY . .

# 接口地址在构建期写死进产物（vite 的机制）。
# 默认留空 = 使用 src/api/http.js 里的内网默认地址 http://172.16.30.159:5000；
# 部署到其他机器时在 docker-compose.yml 的 build.args 里覆盖。
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---------- 阶段二：运行 ----------
FROM docker.m.daocloud.io/library/nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
