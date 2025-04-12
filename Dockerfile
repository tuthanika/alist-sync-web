
# 使用官方Python基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置时区为上海
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制项目的依赖文件
COPY requirements.txt .

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件到容器中
COPY . .

# 设置环境变量
ENV FLASK_ENV=production
ENV PORT=5000

# 暴露应用程序的端口
EXPOSE 5000

# 运行应用程序
CMD ["python", "wsgi.py"] 