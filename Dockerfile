# 使用多阶段构建
# 构建阶段
FROM python:3.12-slim AS builder

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装构建依赖和项目依赖到虚拟环境
RUN python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir --upgrade pip && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

# 最终阶段
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置时区为上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get update && apt-get install -y --no-install-recommends \
    tzdata && \
    rm -rf /var/lib/apt/lists/*

# 从构建阶段复制虚拟环境
COPY --from=builder /venv /venv

# 配置环境变量使用虚拟环境
ENV PATH="/venv/bin:$PATH"

# 复制项目文件到容器中
COPY . .

# 设置环境变量
ENV FLASK_ENV=production
ENV PORT=52441

# 暴露应用程序的端口
EXPOSE 52441

# 运行应用程序
CMD ["python", "startup.py"]