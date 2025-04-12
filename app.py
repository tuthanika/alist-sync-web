from app import create_app
import os
import sys

# 添加当前目录到Python路径，确保可以导入配置模块
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

app = create_app()

if __name__ == '__main__':
    # 启动应用
    port = int(os.environ.get('FLASK_PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port) 