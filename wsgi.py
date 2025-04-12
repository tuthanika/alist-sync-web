import os
import sys
import logging
import pytz
import time

# 设置环境变量
os.environ['TZ'] = 'Asia/Shanghai'
if hasattr(time, 'tzset'):
    time.tzset()

# 设置Python路径
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 创建应用实例
from app import create_app
application = app = create_app()

# 应用环境信息
env = os.environ.get('FLASK_ENV', 'development')
port = int(os.environ.get('PORT', 5000))

# 输出启动信息
print(f"应用启动: 环境={env}, 端口={port}, Python={sys.executable}")
print(f"当前工作目录: {os.getcwd()}")
print(f"时区设置: {os.environ['TZ']}")
print(f"Python路径: {sys.path}")

# 列出所有调度任务
with app.app_context():
    if 'SYNC_MANAGER' in app.config:
        sync_manager = app.config['SYNC_MANAGER']
        jobs = sync_manager.scheduler.get_jobs()
        print(f"调度器中共有 {len(jobs)} 个任务:")
        for job in jobs:
            print(f" - 任务: {job.id}, 下次运行: {job.next_run_time}")

if __name__ == '__main__':
    print(f"启动Flask应用: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=(env == 'development')) 