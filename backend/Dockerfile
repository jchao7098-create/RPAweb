# RPA 项目管理系统 —— 后端镜像（Flask + waitress）
# 基础镜像走 DaoCloud 加速，国内直连不超时
FROM docker.m.daocloud.io/library/python:3.12-slim

# 日志实时输出，不做缓冲（docker logs 才能及时看到）
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 先只拷贝依赖清单：代码改动时可复用已缓存的依赖安装层，加速重建
COPY requirements.txt .

# 内网/国内服务器拉 pypi 慢或超时，取消下一行注释切换到阿里云镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# var/（令牌密钥 + 上传文件）是本地有状态目录，
# 由 docker-compose 挂载到宿主机持久化，镜像里只保证目录存在
RUN mkdir -p var/uploads

EXPOSE 5090

# run.py 默认走 waitress 多线程服务（FLASK_DEBUG 未设置时），适合容器内直接跑
CMD ["python", "run.py"]
