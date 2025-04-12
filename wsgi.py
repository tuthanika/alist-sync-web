import os
import sys
import logging
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
env = os.environ.get('FLASK_ENV', 'production')
port = int(os.environ.get('PORT', 5000))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port) 