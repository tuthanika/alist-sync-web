# 第一阶段：交叉编译环境
FROM --platform=$BUILDPLATFORM tonistiigi/xx:1.3.0 AS xx

FROM --platform=$BUILDPLATFORM python:3.10-slim AS builder

# 导入交叉编译工具链
COPY --from=xx / /

ARG TARGETARCH
RUN xx-apk add --no-cache gcc musl-dev libffi-dev openssl-dev

WORKDIR /app
COPY . .

# 设置交叉编译环境
RUN xx-setup && \
    pip install --no-cache-dir pyinstaller && \
    pip install --no-cache-dir -r requirements.txt && \
    pyinstaller --onefile \
      --name alist-sync-web \
      --add-data 'static:static' \
      --add-data 'templates:templates' \
      --add-data 'VERSION:.' \
      alist-sync-web.py

# 第二阶段：验证输出
FROM --platform=$TARGETPLATFORM alpine:3.18 AS verify
COPY --from=builder /app/dist/alist-sync-web .
RUN [ "/bin/sh", "-c", "file alist-sync-web | grep 'ELF 64-bit LSB executable, ARM aarch64'" ]

# 最终输出阶段
FROM scratch AS export
COPY --from=verify /alist-sync-web /