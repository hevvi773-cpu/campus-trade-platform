# 校园二手交易平台 - Web 服务镜像
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（pymysql/cryptography 编译可能需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用 Docker 缓存层）
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ .

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/', timeout=5)" || exit 1

# 启动命令：gunicorn 生产模式
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "120", "app_v3:app"]
