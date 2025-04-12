import os
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, session, redirect, url_for, request
from app.routes import main_bp, api_bp, auth_bp
from app.utils.data_manager import DataManager
from functools import wraps

# 全局应用实例，用于调度器在无上下文时访问
flask_app = None

def init_logger():
    """配置日志记录器"""
    # 获取当前根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 确保日志目录存在
    log_dir = os.path.join(root_dir, 'data/log')
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志文件路径
    log_file = os.path.join(log_dir, 'alist_sync.log')
    
    # 创建日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 文件处理器 - 按天轮换
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # 清除已有处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def create_app():
    """创建并配置应用"""
    global flask_app
    
    from flask import Flask
    import os
    
    # 创建Flask应用实例
    app = Flask(__name__, static_folder='static')
    
    # 使用内部配置而不是从外部模块导入
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-key-for-alist-sync'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 会话有效期 24 小时
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # 初始化日志
    logger = init_logger()
    app.logger = logger
    app.logger.info("应用初始化开始...")
    
    # 初始化数据管理器
    data_manager = DataManager()
    app.config['DATA_MANAGER'] = data_manager
    
    # 初始化应用(包括调度器)
    from app.app import init_app
    init_app(app)
    
    # 注册蓝图
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # 添加登录检查中间件
    @app.before_request
    def check_login():
        # 定义无需登录的路径
        exempt_routes = ['/auth/login', '/static', '/api']
        
        # 检查路径是否需要登录验证
        if any(request.path.startswith(path) for path in exempt_routes):
            return
        
        # 验证登录状态
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('auth.login'))
    
    # 保存全局应用实例
    flask_app = app
    
    app.logger.info("应用初始化完成")
    return app 