# 第一阶段：构建环境
FROM --platform=$BUILDPLATFORM python:3.10-slim-bullseye AS builder

# 安装构建依赖
RUN apt-get update && \
    apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 安装依赖
RUN pip install --no-cache-dir pyinstaller -r requirements.txt

# 执行构建
RUN pyinstaller --onefile \
    --name alist-sync-web \
    --add-data 'static:static' \
    --add-data 'templates:templates' \
    --add-data 'VERSION:.' \
    alist-sync-web.py

# 第二阶段：输出阶段
FROM scratch AS export
COPY --from=builder /app/dist/alist-sync-web /