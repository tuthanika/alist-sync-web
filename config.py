import os

class Config:
    # 基本配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-alist-sync'
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 86400  # 会话有效期 24 小时
    DEBUG = False
    
    # 应用目录
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    
    # 静态文件配置
    STATIC_FOLDER = 'static'
    
    # 数据目录
    DATA_DIR = os.environ.get('DATA_DIR') or '/app/data'
    
    # 配置文件目录
    CONFIG_DIR = os.path.join(DATA_DIR, 'config')
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_DIR = os.path.join(DATA_DIR, 'log')
    
    # 任务配置
    MAX_CONCURRENT_TASKS = int(os.environ.get('MAX_CONCURRENT_TASKS', 3))
    DEFAULT_RETRY_COUNT = int(os.environ.get('DEFAULT_RETRY_COUNT', 3))
    DEFAULT_BLOCK_SIZE = int(os.environ.get('DEFAULT_BLOCK_SIZE', 10485760))  # 10MB
    
    # 任务日志配置
    KEEP_LOG_DAYS = int(os.environ.get('KEEP_LOG_DAYS', 7))
    TASK_LOGS_DIR = os.path.join(LOG_DIR, 'task_logs')
    
    # 确保目录存在
    @staticmethod
    def init_app(app):
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.CONFIG_DIR, exist_ok=True)
        os.makedirs(Config.TASK_LOGS_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = 'INFO'
    
    # 生产环境应该使用环境变量设置一个强密钥
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'production-secret-key-for-alist-sync'


# 根据环境变量选择配置
config_name = os.environ.get('FLASK_ENV', 'production')
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}

# 默认使用生产配置
Config = config.get(config_name, config['default']) 