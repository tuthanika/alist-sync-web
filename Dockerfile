# 第一阶段：构建环境
FROM python:3.10-alpine AS builder

# 安装构建依赖
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    build-base

# 安装必要工具
RUN pip install --no-cache-dir pyinstaller

# 复制项目文件
WORKDIR /app
COPY . .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 执行构建
RUN pyinstaller --onefile \
    --name alist-sync-web \
    --add-data 'static:static' \
    --add-data 'templates:templates' \
    --add-data 'VERSION:.' \
    alist-sync-web.py

# 第二阶段：整理输出
FROM alpine:3.18

# 复制构建结果
COPY --from=builder /app/dist/alist-sync-web /app/alist-sync-web

# 设置输出目录
WORKDIR /app
RUN chmod +x alist-sync-web

# 设置输出路径
VOLUME /output

CMD cp alist-sync-web /output/