FROM python:3.11-slim

WORKDIR /app

# 系统依赖：OpenCV/rapidocr 运行所需 + gcc
# 国内用阿里云 Debian 镜像加速（同时兼容新旧 sources 格式）
# 构建时强制清空代理：宿主机 Clash 端口常只绑 127.0.0.1，BuildKit 注入的
# host.docker.internal:7897/17890 会导致 apt 全线 Connection refused。
RUN export http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= all_proxy= no_proxy='*' NO_PROXY='*'; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
        sed -i 's/security.debian.org/mirrors.aliyun.com\/debian-security/g' /etc/apt/sources.list; \
    fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
        sed -i 's/security.debian.org/mirrors.aliyun.com\/debian-security/g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 gcc curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 先装 CPU-only torch（避开 GPU/CUDA 几 GB；bge 走 CPU 推理够用），再装其余依赖
RUN export http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= all_proxy= no_proxy='*' NO_PROXY='*'; \
    pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu --trusted-host download.pytorch.org && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

COPY . .

EXPOSE 8001
# WORKDIR=/app，import app.main 即可；配置优先读环境变量（compose env_file 注入）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
