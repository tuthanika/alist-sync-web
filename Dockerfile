# 使用多阶段构建
FROM --platform=$BUILDPLATFORM python:${PYTHON_VERSION}-alpine AS builder

# 安装构建依赖
RUN apk add --no-cache \
    build-base \
    zlib-dev \
    libffi-dev \
    openssl-dev

# 安装 PyInstaller
RUN pip install --no-cache-dir pyinstaller

WORKDIR /app
COPY . .

# 构建可执行文件
RUN pyinstaller \
    --name "alist-sync-$TARGETARCH" \
    --onefile \
    --add-data "static:static" \
    --add-data "templates:templates" \
    alist-sync-web.py

FROM scratch AS export
COPY --from=builder /app/dist /