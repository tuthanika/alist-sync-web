from flask import Flask, render_template, request,jsonify,session,redirect,url_for
from flask_bootstrap import Bootstrap
import logging
import subprocess
import os
import json
# import datetime
# import pytz
import croniter, datetime, time
from functools import wraps
from crontab import CronTab
# from crontab import CronTab
# import datetime

from apscheduler.triggers.cron import CronTrigger


from alist_sync import create_connection, get_token, get_storage_list

import signal
# 这里假设 alist_sync.py 所在模块可以正确导入，实际中可能需要调整导入路径


app = Flask(__name__)
app.secret_key = os.urandom(24) # 用于session加密
Bootstrap(app)


# 设置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



# 假设配置数据存储在当前目录下的config_data目录中，你可以根据实际需求修改
STORAGE_DIR = os.path.join(app.root_path, 'config_data')
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

# 用户配置文件路径
USER_CONFIG_FILE = os.path.join(os.path.dirname(__file__),STORAGE_DIR, 'users_config.json')

# 确保配置目录存在
os.makedirs(os.path.dirname(USER_CONFIG_FILE), exist_ok=True)





# 如果用户配置文件不存在,创建默认配置
if not os.path.exists(USER_CONFIG_FILE):
    default_config = {
        "users": [
            {
                "username": "admin",
                "password": "admin"
            }
        ]
    }
    with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)

def load_users():
    """加载用户配置"""
    try:
        with open(USER_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载用户配置失败: {e}")
        return {"users": []}

def save_users(config):
    """保存用户配置"""
    try:
        with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存用户配置失败: {e}")
        return False

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# 默认路由重定向到登录页
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


# 登录页面路由
@app.route('/login')
def login():
    return render_template('login.html')


# 登录接口
@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'code': 400, 'message': '用户名和密码不能为空'})

        # 加载用户配置
        config = load_users()

        # 查找用户
        user = next((user for user in config['users']
                     if user['username'] == username
                     and user['password'] == password), None)

        if user:
            session['user_id'] = username
            return jsonify({'code': 200, 'message': '登录成功'})
        else:
            return jsonify({'code': 401, 'message': '用户名或密码错误'})

    except Exception as e:
        print(f"登录失败: {e}")
        return jsonify({'code': 500, 'message': '服务器错误'})


# 检查登录状态接口
@app.route('/api/check-login')
def check_login():
    if 'user_id' in session:
        return jsonify({'code': 200, 'message': 'logged in'})
    return jsonify({'code': 401, 'message': 'not logged in'})


# 获取当前用户信息接口
@app.route('/api/current-user')
@login_required
def current_user():
    try:
        username = session['user_id']
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'username': username
            }
        })
    except Exception as e:
        print(f"获取当前用户信息失败: {e}")
        return jsonify({'code': 500, 'message': '服务器错误'})
# 修改密码接口
@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    try:
        data = request.get_json()
        old_username = data.get('oldUsername')
        new_username = data.get('newUsername')
        old_password = data.get('oldPassword')
        new_password = data.get('newPassword')

        if not all([old_username, new_username, old_password, new_password]):
            return jsonify({'code': 400, 'message': '所有字段都不能为空'})

        # 加载用户配置
        config = load_users()

        # 查找当前用户
        username = session['user_id']
        user = next((user for user in config['users']
                     if user['username'] == username), None)

        if not user:
            return jsonify({'code': 404, 'message': '用户不存在'})

        # 验证原密码
        if user['password'] != old_password:
            return jsonify({'code': 400, 'message': '原密码错误'})

        # 如果修改了用户名,确保新用户名不存在
        if old_username != new_username:
            exists_user = next((u for u in config['users']
                                if u['username'] == new_username
                                and u != user), None)
            if exists_user:
                return jsonify({'code': 400, 'message': '新用户名已存在'})

        # 更新用户名和密码
        user['username'] = new_username
        user['password'] = new_password

        # 保存配置
        if save_users(config):
            # 如果修改了用户名,更新session
            if old_username != new_username:
                session['user_id'] = new_username
            return jsonify({'code': 200, 'message': '修改成功'})
        else:
            return jsonify({'code': 500, 'message': '保存配置失败'})

    except Exception as e:
        print(f"修改密码失败: {e}")
        return jsonify({'code': 500, 'message': '服务器错误'})


# 登出接口
@app.route('/api/logout')
def logout():
    session.clear()
    return jsonify({'code': 200, 'message': 'success'})


# 保存基础连接配置接口
@app.route('/api/save-base-config', methods=['POST'])
@login_required
def save_base_config():
    data = request.get_json()
    base_url = data.get('baseUrl')
    username = data.get('username')
    password = data.get('password')
    config_file_path = os.path.join(STORAGE_DIR, 'base_config.json')
    try:
        with open(config_file_path, 'w') as f:
            json.dump({
                "baseUrl": base_url,
                "username": username,
                "password": password
            }, f)
        return jsonify({"code": 200, "message": "基础配置保存成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"保存失败: {str(e)}"})

# 查询基础连接配置接口
@app.route('/api/get-base-config', methods=['GET'])
@login_required
def get_base_config():
    config_file_path = os.path.join(STORAGE_DIR, 'base_config.json')
    try:
        with open(config_file_path, 'r') as f:
            config_data = json.load(f)
        return jsonify({"code": 200, "data": config_data})
    except FileNotFoundError:
        return jsonify({"code": 404, "message": "配置文件不存在"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"读取配置失败: {str(e)}"})

@app.route('/api/get-sync-config', methods=['GET'])
@login_required
def get_sync_config():
    config_file_path = os.path.join(STORAGE_DIR, 'sync_config.json')
    try:
        with open(config_file_path, 'r') as f:
            config_data = json.load(f)
        return jsonify({"code": 200, "data": config_data})
    except FileNotFoundError:
        return jsonify({"code": 404, "message": "配置文件不存在"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"读取配置失败: {str(e)}"})




# 定义超时处理函数
def timeout_handler(signum, frame):
    raise TimeoutError("连接测试超时")
# 测试连接接口
@app.route('/api/test-connection', methods=['POST'])
@login_required
def test_connection():
    try:


        data = request.get_json()
        base_url = data.get('baseUrl')
        username = data.get('username')
        password = data.get('password')
        conn = create_connection(base_url)
        token = get_token(conn, "/api/auth/login", username, password)


        # 这里加入真实的连接测试逻辑，比如根据不同协议（http、https等）利用 requests 库等去尝试连接对应服务，示例中暂时省略具体实现
        # 假设连接测试成功，取消定时器，并返回对应状态码和消息
        # signal.alarm(0)  # 取消定时器

        if token:
            return jsonify({"code": 200, "message": "连接测试成功"})
        else:
            return jsonify({"code": 500, "message": f"数据解析错误: 地址或用户名或密码错误"})
    except TimeoutError as te:
        # 如果超时，返回相应的超时失败提示
        return jsonify({"code": 504, "message": str(te)})
    except Exception as e:
        # 如果解析JSON数据出错等其他异常情况，返回相应错误提示
        return jsonify({"code": 500, "message": f"数据解析错误: {str(e)}"})


# 保存同步配置接口
@app.route('/api/save-sync-config', methods=['POST'])
@login_required
def save_sync_config():
    data = request.get_json()
    sync_config_file_path = os.path.join(STORAGE_DIR,'sync_config.json')
    try:
        with open(sync_config_file_path, 'w') as f:
            json.dump(data, f)
        return jsonify({"code": 200, "message": "同步配置保存成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"保存失败: {str(e)}"})





# 假设存储器列表数据也是存储在文件中，这里模拟返回一些示例数据，你可根据实际替换读取逻辑
@app.route('/api/storages', methods=['GET'])
@login_required
def get_storages():
    config = get_base_config()
    data = config.get_json().get("data")

    # data = request.get_json()
    base_url = data.get('baseUrl')
    username = data.get('username')
    password = data.get('password')
    conn = create_connection(base_url)
    token = get_token(conn, "/api/auth/login", username, password)

    storage_list = get_storage_list(conn, token)
    return jsonify({"code": 200, "data": storage_list})


# 执行任务接口
@app.route('/api/run-task', methods=['POST'])
@login_required
def run_task():
    # 这里可以添加真实的任务执行逻辑，比如调用相关同步任务执行的函数等，简化示例直接返回成功
    return jsonify({"code": 200, "message": "任务已启动"})


@app.route('/api/next-run-time', methods=['POST'])
def next_run_time():
    # Cron 表达式解析与时间计算
    try:
        data = request.get_json()
        cron_expression = data.get('cron')
        if not cron_expression:
            return jsonify({"code": 400, "message": "缺少cron参数"}), 400
        # 简单校验，如果末尾是?就去除（只是简单处理，更严谨校验可完善此处）
        # 替换问号为星号
        # modified_cron = cron_expression.replace('?', '*')
        # 找到第一个空格的索引位置，然后从该位置往后取字符串
        # index_of_first_space = modified_cron.find(' ')
        # new_cron = modified_cron[index_of_first_space + 1:]
        next_time_list = CrontabRunNextTime(cron_expression)
        return jsonify({"code": 200, "data": next_time_list})
    except Exception as e:
        return jsonify({"code": 500, "message": f"解析出错: {str(e)}"}), 500




def datetime_to_timestamp(timestring, format="%Y-%m-%d %H:%M:%S"):
    """ 将普通时间格式转换为时间戳(10位), 形如 '2016-05-05 20:28:54'，由format指定 """
    try:
        # 转换成时间数组
        timeArray = time.strptime(timestring, format)
    except Exception:
        raise
    else:
        # 转换成10位时间戳
        return int(time.mktime(timeArray))

def get_current_timestamp():
    """ 获取本地当前时间戳(10位): Unix timestamp：是从1970年1月1日（UTC/GMT的午夜）开始所经过的秒数，不考虑闰秒 """
    return int(time.mktime(datetime.datetime.now().timetuple()))

def timestamp_after_timestamp(timestamp=None, seconds=0, minutes=0, hours=0, days=0):
    """ 给定时间戳(10位),计算该时间戳之后多少秒、分钟、小时、天的时间戳(本地时间) """
    # 1. 默认时间戳为当前时间
    timestamp = get_current_timestamp() if timestamp is None else timestamp
    # 2. 先转换为datetime
    d1 = datetime.datetime.fromtimestamp(timestamp)
    # 3. 根据相关时间得到datetime对象并相加给定时间戳的时间
    d2 = d1 + datetime.timedelta(seconds=int(seconds), minutes=int(minutes), hours=int(hours), days=int(days))
    # 4. 返回某时间后的时间戳
    return int(time.mktime(d2.timetuple()))


def timestamp_datetime(timestamp, format='%Y-%m-%d %H:%M:%S'):
    """ 将时间戳(10位)转换为可读性的时间 """
    # timestamp为传入的值为时间戳(10位整数)，如：1332888820
    timestamp = time.localtime(timestamp)
    # 经过localtime转换后变成
    ## time.struct_time(tm_year=2012, tm_mon=3, tm_mday=28, tm_hour=6, tm_min=53, tm_sec=40, tm_wday=2, tm_yday=88, tm_isdst=0)
    # 最后再经过strftime函数转换为正常日期格式。
    return time.strftime(format, timestamp)

def CrontabRunNextTime(sched, timeFormat="%Y-%m-%d %H:%M:%S", queryTimes=5):
    """计算定时任务下次运行时间
    sched str: 定时任务时间表达式
    timeFormat str: 格式为"%Y-%m-%d %H:%M"
    queryTimes int: 查询下次运行次数
    """
    try:
        now = datetime.datetime.now()
    except ValueError:
        raise
    else:
        # 以当前时间为基准开始计算
        cron = croniter.croniter(sched, now)
        return [ cron.get_next(datetime.datetime).strftime(timeFormat) for i in range(queryTimes) ]

def CrontabRunTime(sched, ctime, timeFormat="%Y-%m-%d %H:%M:%S"):
    """计算定时任务运行次数
    sched str: 定时任务时间表达式
    ctime str: 定时任务创建的时间，与timeFormat格式对应
    timeFormat str: 格式为"%Y-%m-%d %H:%M"
    """
    try:
        ctimeStrp = datetime.datetime.strptime(ctime, timeFormat)
    except ValueError:
        raise
    else:
        # 根据定时任务创建时间开始计算
        cron = croniter.croniter(sched, ctimeStrp)
        now = get_current_timestamp()
        num = 0
        while 1:
            timestring = cron.get_next(datetime.datetime).strftime(timeFormat)
            timestamp = datetime_to_timestamp(timestring, "%Y-%m-%d %H:%M:%S")
            if timestamp > now:
                break
            else:
                num += 1
        return num




# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':
#         # 从页面获取参数
#         base_url = request.form.get('base_url')
#         username = request.form.get('username')
#         password = request.form.get('password')
#         cron_schedule = request.form.get('cron_schedule')
#         sync_delete_action = request.form.get('sync_delete_action')
#         dir_pairs = request.form.get('dir_pairs')
#
#         # 设置环境变量，以便被原Python代码读取
#         os.environ['BASE_URL'] = base_url
#         os.environ['USERNAME'] = username
#         os.environ['PASSWORD'] = password
#         os.environ['CRON_SCHEDULE'] = cron_schedule
#         os.environ['SYNC_DELETE_ACTION'] = sync_delete_action
#         os.environ['DIR_PAIRS'] = dir_pairs
#
#         # 执行原Python代码，这里假设原Python代码文件名为your_code.py
#         result = subprocess.run(['python', 'alist-sync-test.py'], capture_output=True, text=True)
#
#         # 读取并记录Python代码执行过程中打印的内容作为日志
#         logger.info(result.stdout)
#
#         return f"执行结果日志已记录，你可以查看日志详情。<br>返回码: {result.returncode}"
#     return render_template('index.html')
#





if __name__ == '__main__':
    app.run(debug=True)