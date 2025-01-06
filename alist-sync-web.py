from fastapi import FastAPI, Request, Response, HTTPException, Depends, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from pydantic import BaseModel
import uvicorn
import logging
import os
import json
from pathlib import Path  # 使用内置 pathlib

import croniter, datetime, time
from functools import wraps

# 动态导入alist-sync-ql.py
import importlib.util
import sys

from typing import Dict, List, Optional, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from logging.handlers import TimedRotatingFileHandler
import glob

import hashlib
import secrets
import base64

import schedule
from threading import Thread

import aiofiles  # 用于异步文件操作

# 创建一个全局的调度器
scheduler = BackgroundScheduler()
scheduler.start()


def import_from_file(module_name: str, file_path: str) -> Any:
    """动态导入模块"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 导入AlistSync类
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    alist_sync = import_from_file('alist_sync',
                                     os.path.join(current_dir, 'alist_sync.py'))
    AlistSync = alist_sync.AlistSync
except Exception as e:
    print(f"导入alist_sync.py失败: {e}")
    print(f"当前目录: {current_dir}")
    print(f"尝试导入的文件路径: {os.path.join(current_dir, 'alist_sync.py')}")
    raise

app = FastAPI()
# 使用固定的密钥，避免重启后 session 失效
SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="alist_sync_session",
    max_age=86400,  # 1天过期
    same_site="lax",
    https_only=False
)
templates = Jinja2Templates(directory="templates")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 修改路径处理
STORAGE_DIR = Path(app.root_path) / 'data' / 'config'
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# 用户配置文件路径
USER_CONFIG_FILE = Path(__file__).parent / STORAGE_DIR / 'users_config.json'

# 确保配置目录存在
USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)


# 添加密码加密和验证函数
def hash_password(password: str) -> str:
    """
    使用 SHA-256 加盐加密密码
    返回格式: base64(salt):base64(hash)
    """
    salt = secrets.token_bytes(16)  # 生成16字节的随机盐值
    h = hashlib.sha256()
    h.update(salt)
    h.update(password.encode('utf-8'))
    hash_value = h.digest()
    # 将盐值和哈希值用base64编码并用冒号连接
    return f"{base64.b64encode(salt).decode()}:{base64.b64encode(hash_value).decode()}"


def verify_password(password: str, hash_str: str) -> bool:
    """验证密码是否正确"""
    try:
        # 分离盐值和哈希值
        salt_b64, hash_b64 = hash_str.split(':')
        salt = base64.b64decode(salt_b64)
        stored_hash = base64.b64decode(hash_b64)

        # 使用相同的盐值重新计算哈希
        h = hashlib.sha256()
        h.update(salt)
        h.update(password.encode('utf-8'))
        calculated_hash = h.digest()

        # 比较哈希值
        return secrets.compare_digest(calculated_hash, stored_hash)
    except Exception:
        return False


# 如果用户配置文件不存在,创建默认配置
if not os.path.exists(USER_CONFIG_FILE):
    default_config = {
        "users": [
            {
                "username": "admin",
                "password": hash_password("admin")
            }
        ]
    }
    with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)


async def load_users():
    """加载用户配置"""
    try:
        async with aiofiles.open(USER_CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
    except Exception as e:
        logger.error(f"加载用户配置失败: {e}")
        return {"users": []}


async def save_users(config):
    """保存用户配置"""
    try:
        async with aiofiles.open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"保存用户配置失败: {e}")
        return False


# 定义请求模型
class LoginCredentials(BaseModel):
    username: str
    password: str


# 默认路由
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request})


# 登录页面
@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# 登录API
@app.post("/api/login")
async def api_login(credentials: LoginCredentials, request: Request):
    try:
        if not credentials.username or not credentials.password:
            raise HTTPException(status_code=400, detail="用户名和密码不能为空")
            
        config = await load_users()
        user = next((user for user in config['users']
                     if user['username'] == credentials.username), None)

        if user and verify_password(credentials.password, user['password']):
            request.session['user_id'] = credentials.username
            return JSONResponse({"code": 200, "message": "登录成功"})
        else:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 登录验证依赖
async def get_current_user(request: Request):
    if "user_id" not in request.session:
        raise HTTPException(status_code=401, detail="未登录")
    return request.session["user_id"]


# 需要登录的API示例
@app.get("/api/current-user")
async def current_user(user: str = Depends(get_current_user)):
    return {
        "code": 200,
        "message": "success",
        "data": {
            "username": user
        }
    }


# 检查登录状态接口
@app.get('/api/check-login')
async def check_login(request: Request):
    if 'user_id' in request.session:
        return {'code': 200, 'message': 'logged in'}
    return {'code': 401, 'message': 'not logged in'}


# 修改密码接口
@app.post('/api/change-password')
async def change_password(
    request: Request,
    credentials: dict,
    current_user: str = Depends(get_current_user)
):
    try:
        old_username = credentials.get('oldUsername')
        new_username = credentials.get('newUsername')
        old_password = credentials.get('oldPassword')
        new_password = credentials.get('newPassword')

        if not all([old_username, new_username, old_password, new_password]):
            raise HTTPException(status_code=400, detail='所有字段都不能为空')

        # 加载用户配置
        config = await load_users()

        # 查找当前用户
        username = current_user
        user = next((user for user in config['users']
                     if user['username'] == username), None)

        if not user:
            raise HTTPException(status_code=404, detail='用户不存在')

        # 验证原密码
        if not verify_password(old_password, user['password']):
            raise HTTPException(status_code=400, detail='原密码错误')

        # 如果修改了用户名,确保新用户名不存在
        if old_username != new_username:
            exists_user = next((u for u in config['users']
                                if u['username'] == new_username
                                and u != user), None)
            if exists_user:
                raise HTTPException(status_code=400, detail='新用户名已存在')

        # 更新用户名和密码
        user['username'] = new_username
        user['password'] = hash_password(new_password)

        # 保存配置
        if await save_users(config):
            # 如果修改了用户名,更新session
            if old_username != new_username:
                request.session['user_id'] = new_username
            return {'code': 200, 'message': '修改成功'}
        else:
            raise HTTPException(status_code=500, detail='保存配置失败')

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 登出接口
@app.post('/api/logout')
async def logout(request: Request):
    request.session.clear()
    response = JSONResponse({'code': 200, 'message': 'success'})
    return response


# 保存基础连接配置接口
@app.post('/api/save-base-config')
async def save_base_config(
    request: Request,
    data: dict,
    current_user: str = Depends(get_current_user)
):
    try:
        base_url = data.get('baseUrl')
        username = data.get('username')
        password = data.get('password')
        config_file_path = STORAGE_DIR / 'base_config.json'

        config_data = {
            "baseUrl": base_url,
            "username": username,
            "password": password
        }

        async with aiofiles.open(config_file_path, 'w') as f:
            await f.write(json.dumps(config_data, indent=2))
        return {"code": 200, "message": "基础配置保存成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


# 查询基础连接配置接口
@app.get('/api/get-base-config')
async def get_base_config(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        config_file_path = STORAGE_DIR / 'base_config.json'

        async with aiofiles.open(config_file_path, 'r') as f:
            content = await f.read()
            config_data = json.loads(content)
        return {"code": 200, "data": config_data}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="配置文件不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取配置失败: {str(e)}")


@app.get('/api/get-sync-config')
async def get_sync_config(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    config_file_path = STORAGE_DIR / 'sync_config.json'
    try:
        async with aiofiles.open(config_file_path, 'r') as f:
            content = await f.read()
            config_data = json.loads(content)
        return {"code": 200, "data": config_data}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="配置文件不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取配置失败: {str(e)}")


# 定义超时处理函数
def timeout_handler(signum, frame):
    raise TimeoutError("连接测试超时")


# 测试连接接口
@app.post('/api/test-connection')
async def test_connection(
    request: Request,
    data: dict,
    current_user: str = Depends(get_current_user)
):
    try:
        base_url = data.get('baseUrl')
        username = data.get('username')
        password = data.get('password')

        # 创建 AlistSync 实例
        alist = AlistSync(base_url, username, password)

        # 尝试登录
        if await alist.login():
            return {"code": 200, "message": "连接测试成功"}
        else:
            raise HTTPException(status_code=500, detail="地址或用户名或密码错误")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")
    finally:
        if 'alist' in locals():
            await alist.close()


# 添加以下函数来管理定时任务
async def schedule_sync_tasks():
    """从配置文件读取并调度所有同步任务"""
    try:
        # 清除所有现有的任务
        scheduler.remove_all_jobs()

        # 加载同步配置
        sync_config = await load_sync_config()
        if not sync_config or 'tasks' not in sync_config:
            logger.warning("没有找到有效的同步任务配置")
            return

        # 为每个任务创建调度
        for task in sync_config['tasks']:
            if 'cron' not in task:
                logger.warning(f"任务 {task.get('taskName', 'unknown')} 没有配置cron表达式")
                continue

            try:
                job_id = f"sync_task_{task['id']}"
                scheduler.add_job(
                    func=execute_sync_task,
                    trigger=CronTrigger.from_crontab(task['cron']),
                    id=job_id,
                    replace_existing=True,
                    args=[task['id']]
                )
                logger.info(f"成功调度任务 {task['taskName']}, ID: {job_id}, Cron: {task['cron']}")
            except Exception as e:
                logger.error(f"调度任务 {task.get('taskName', 'unknown')} 失败: {str(e)}")

    except Exception as e:
        logger.error(f"调度同步任务时发生错误: {str(e)}")


# 修改保存同步配置接口，使其在保存后重新调度任务
@app.post('/api/save-sync-config')
async def save_sync_config(
    request: Request,
    data: dict,
    current_user: str = Depends(get_current_user)
):
    sync_config_file_path = STORAGE_DIR / 'sync_config.json'
    try:
        async with aiofiles.open(sync_config_file_path, 'w') as f:
            await f.write(json.dumps(data, indent=2))
        # 重新调度所有任务    
        await schedule_sync_tasks()
        return {"code": 200, "message": "同步配置保存成功并已更新调度"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


# 获取存储列表接口
@app.get('/api/storages')
async def get_storages(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        base_config = await load_base_config()
        if not base_config:
            raise HTTPException(status_code=400, detail="请先配置基础连接信息")

        alist = AlistSync(
            base_url=base_config.get('baseUrl'),
            username=base_config.get('username'),
            password=base_config.get('password')
        )

        if not await alist.login():
            raise HTTPException(status_code=401, detail="登录失败")

        # 使用 httpx 客户端发送请求
        response = await alist.client.get(
            f"{alist.base_url}/api/admin/storage/list",
            headers={
                "Authorization": alist.token,
                "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
                "Content-Type": "application/json"
            }
        )
        data = response.json()
        if data.get("code") == 200:
            content = data.get("data", [])
            storage_list = content.get("content", [])
            storages = [item["mount_path"] for item in storage_list]
        else:
            raise HTTPException(status_code=500, detail="获取存储列表失败")

        await alist.close()

        return {
            "code": 200,
            "data": storages
        }
    except Exception as e:
        logger.error(f"获取存储列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取存储列表失败: {str(e)}")
    finally:
        if 'alist' in locals():
            await alist.close()


@app.post('/api/next-run-time')
async def next_run_time(
    request: Request,
    data: dict,
    current_user: str = Depends(get_current_user)
):
    # Cron 表达式解析与时间计算
    try:
        cron_expression = data.get('cron')
        if not cron_expression:
            raise HTTPException(status_code=400, detail="缺少cron参数")
        next_time_list = crontab_run_next_time(cron_expression)
        return {"code": 200, "data": next_time_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析出错: {str(e)}")


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
    return time.strftime(format, timestamp)


def crontab_run_next_time(cron_expression, timeFormat="%Y-%m-%d %H:%M:%S", queryTimes=5):
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
        cron = croniter.croniter(cron_expression, now)
        return [cron.get_next(datetime.datetime).strftime(timeFormat) for i in range(queryTimes)]


# def CrontabRunTime(sched, ctime, timeFormat="%Y-%m-%d %H:%M:%S"):
#     """计算定时任务运行次数
#     sched str: 定时任务时间表达式
#     ctime str: 定时任务创建的时间，与timeFormat格式对应
#     timeFormat str: 格式为"%Y-%m-%d %H:%M"
#     """
#     try:
#         ctimeStrp = datetime.datetime.strptime(ctime, timeFormat)
#     except ValueError:
#         raise
#     else:
#         # 根据定时任务创建时间开始计算
#         cron = croniter.croniter(sched, ctimeStrp)
#         now = get_current_timestamp()
#         num = 0
#         while 1:
#             timestring = cron.get_next(datetime.datetime).strftime(timeFormat)
#             timestamp = datetime_to_timestamp(timestring, "%Y-%m-%d %H:%M:%S")
#             if timestamp > now:
#                 break
#             else:
#                 num += 1
#         return num


# 执行任务接口
@app.post('/api/execute-task')
async def execute_task(
    request: Request,
    data: dict,
    current_user: str = Depends(get_current_user)
):
    try:
        task_id = data.get('taskId')
        if not task_id:
            raise HTTPException(status_code=400, detail="缺少taskId参数")

        # 执行同步任务
        if execute_sync_task(task_id):
            return {"code": 200, "message": "任务执行成功"}
        else:
            raise HTTPException(status_code=500, detail="任务执行失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行任务失败: {str(e)}")


# 获取任务状态接口
@app.get('/api/task-status')
async def get_task_status(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        jobs = scheduler.get_jobs()
        status_list = []
        for job in jobs:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else None
            status_list.append({
                'id': job.id,
                'next_run': next_run,
                'running': job.pending
            })
        return {"code": 200, "data": status_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


# 获取任务日志接口
@app.get('/api/task-logs/{task_id}')
async def get_task_logs(
    task_id: str,
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        # 这里实现获取指定任务的日志逻辑
        logs = []  # 从日志文件或数据库中获取日志
        return {"code": 200, "data": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务日志失败: {str(e)}")


async def execute_sync_task(id: str = None) -> bool:
    """执行同步任务"""
    task_name = "未知任务"
    try:
        # 加载基础配置
        base_config = await load_base_config()
        if not base_config:
            logger.error("基础配置为空，无法执行同步任务")
            return False
  
        logger.info(f"已加载基础配置")
  
        # 清除可能存在的旧环境变量
        for i in range(1, 51):
            if f'DIR_PAIRS{i}' in os.environ:
                del os.environ[f'DIR_PAIRS{i}']
        if 'DIR_PAIRS' in os.environ:
            del os.environ['DIR_PAIRS']
  
        # 设置基础环境变量
        os.environ['BASE_URL'] = base_config.get('baseUrl', '')
        os.environ['USERNAME'] = base_config.get('username', '')
        os.environ['PASSWORD'] = base_config.get('password', '')
  
        # 加载同步配置
        sync_config = await load_sync_config()
        if not sync_config:
            logger.error("同步配置为空，无法执行同步任务")
            return False
  
        # 处理任务列表
        tasks = sync_config.get('tasks', [])
        if not tasks:
            logger.error("没有配置同步任务")
            return False
  
        for task in tasks:
            try:
                if id is None or id == task['id']:
                    task_name = task.get('taskName', '未知任务')
                    sync_del_action = task.get('syncDelAction', 'none')
                    logger.info(f"[{task_name}] 开始处理任务，差异处置策略: {sync_del_action}")
  
                    # 更新环境变量中的差异处置策略
                    os.environ['SYNC_DELETE_ACTION'] = sync_del_action
  
                    if task['syncMode'] == 'data':
                        # 数据同步模式：一个源路径同步到多个目标路径
                        src_path = task['sourceStorage']
                        dst_paths = task['targetStorages']
                        sync_dirs = task['syncDirs']
                        exclude_dirs = task.get('excludeDirs', '')
  
                        # 构建同步目录对
                        dir_pairs = []
                        for dst_path in dst_paths:
                            src_dir = f"{src_path}/{sync_dirs}".replace('//', '/')
                            dst_dir = f"{dst_path}/{sync_dirs}".replace('//', '/')
                            dir_pairs.append(f"{src_dir}:{dst_dir}")
  
                        # 调用同步函数
                        await alist_sync.main(";".join(dir_pairs), sync_del_action, exclude_dirs)
  
                    elif task['syncMode'] == 'file':
                        dir_pairs = ''
                        exclude_dirs = task['excludeDirs']
                        os.environ['EXCLUDE_DIRS'] = exclude_dirs
                        # 文件同步模式：多个源路径同步到对应的目标路径
                        paths = task['paths']
                        for path in paths:
                            dir_pair = f"{path['srcPath']}:{path['dstPath']}"
                            if 'DIR_PAIRS' in os.environ:
                                os.environ['DIR_PAIRS'] += f";{dir_pair}"
                            else:
                                os.environ['DIR_PAIRS'] = dir_pair
  
                            if dir_pairs != '':
                                dir_pairs += f";{dir_pair}"
                            else:
                                dir_pairs = dir_pair
  
                            logger.info(f"[{task_name}] 添加同步目录对: {dir_pair}")
                        await alist_sync.main(dir_pairs, sync_del_action, exclude_dirs)
  
            except KeyError as e:
                logger.error(f"[{task_name}] 任务配置错误: {e}")
                continue
  
        # 检查是否有有效的同步目录对
        if 'DIR_PAIRS' not in os.environ or not os.environ['DIR_PAIRS']:
            logger.error("没有有效的同步目录对")
            return False
  
        logger.info(f"[{task_name}] 开始执行同步任务，同步目录对: {os.environ['DIR_PAIRS']}")
  
        # 调用 alist_sync 的 main 函数
        await alist_sync.main()
        logger.info(f"[{task_name}] 同步任务执行完成")
        return True
  
    except Exception as e:
        logger.error(f"[{task_name}] 执行同步任务失败: {str(e)}")
        return False


async def load_base_config() -> dict:
    """加载基础配置"""
    try:
        config_file_path = STORAGE_DIR / 'base_config.json'
        if not config_file_path.exists():
            logger.warning(f"基础配置文件不存在: {config_file_path}")
            return {}

        async with aiofiles.open(config_file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            config = json.loads(content)
            logger.info(f"成功加载基础配置")
            return config
    except Exception as e:
        logger.error(f"加载基础配置失败: {e}")
        return {}


async def load_sync_config() -> dict:
    """加载同步配置"""
    try:
        sync_config_file_path = STORAGE_DIR / 'sync_config.json'
        if not sync_config_file_path.exists():
            logger.warning(f"同步配置文件不存在: {sync_config_file_path}")
            return {"tasks": []}

        async with aiofiles.open(sync_config_file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            config = json.loads(content)
            logger.info(f"成功加载同步配置: {config}")
            return config
    except Exception as e:
        logger.error(f"加载同步配置失败: {e}")
        return {"tasks": []}


# 在 if __name__ == '__main__': 之前添加初始化调度的代码
async def init_scheduler():
    """初始化调度器"""
    try:
        # 加载同步配置
        sync_config = await load_sync_config()
        if not sync_config or 'tasks' not in sync_config:
            logger.warning("没有找到有效的同步任务配置")
            return

        # 清除现有的任务
        schedule.clear()

        # 为每个任务创建调度
        for task in sync_config['tasks']:
            if 'cron' not in task:
                continue
                
            # 解析cron表达式并设置对应的schedule
            cron = task['cron'].split()
            if len(cron) == 5:
                minute, hour, day, month, day_of_week = cron
                
                # 设置定时任务
                if minute != '*':
                    schedule.every().minute.at(f":{minute}").do(
                        lambda: asyncio.create_task(execute_sync_task(task['id']))
                    )
                if hour != '*':
                    schedule.every().hour.at(f":{minute}").do(
                        lambda: asyncio.create_task(execute_sync_task(task['id']))
                    )
  
        # 启动调度器线程
        def run_async_scheduler():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_scheduler())
        
        scheduler_thread = Thread(target=run_async_scheduler, daemon=True)
        scheduler_thread.start()
        
    except Exception as e:
        logger.error(f"初始化调度器失败: {str(e)}")


# 修改日志配置部分
def setup_logger():
    """配置日志记录器"""
    # 创建日志目录
    log_dir = os.path.join(app.root_path, 'data/log')
    os.makedirs(log_dir, exist_ok=True)

    # 设置日志文件路径
    log_file = os.path.join(log_dir, 'alist_sync.log')

    # 创建 TimedRotatingFileHandler
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )

    # 创建控制台处理器
    console_handler = logging.StreamHandler()

    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除现有的处理器
    logger.handlers.clear()

    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 在 app 创建后调用
logger = setup_logger()


# 添加获取日志的接口
@app.get('/api/logs')
async def get_logs(
    request: Request,
    date: str = None,
    current_user: str = Depends(get_current_user)
):
    try:
        date_str = date

        # 构建日志文件路径
        log_dir = Path(app.root_path) / 'data' / 'log'

        # 如果是请求当前日志或没有指定日期
        if not date_str or date_str == 'current':
            log_file = log_dir / 'alist_sync.log'
            date_str = 'current'
        else:
            # 历史日志文件
            log_file = log_dir / f'alist_sync.log.{date_str}'

        logs = []
        if log_file.exists():
            async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            logs.append({
                'date': date_str,
                'content': content
            })

        return {
            'code': 200,
            'data': logs
        }

    except Exception as e:
        logger.error(f"获取日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")


async def run_scheduler():
    while True:
        # 获取所有待执行的任务
        jobs = schedule.get_jobs()
        for job in jobs:
            if job.should_run:
                try:
                    # 异步执行任务
                    if hasattr(job, 'job_func'):
                        if asyncio.iscoroutinefunction(job.job_func):
                            await job.job_func()
                        else:
                            job.job_func()
                    job.last_run = datetime.datetime.now()
                    job._schedule_next_run()
                except Exception as e:
                    logger.error(f"执行调度任务失败: {str(e)}")
        await asyncio.sleep(1)

def init_config_files():
    """初始化配置文件"""
    try:
        # 确保配置目录存在
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 初始化同步配置文件
        sync_config_file = STORAGE_DIR / 'sync_config.json'
        if not sync_config_file.exists():
            default_sync_config = {
                "tasks": []
            }
            sync_config_file.write_text(json.dumps(default_sync_config, indent=2))
            logger.info("创建默认同步配置文件")
            
        # 初始化基础配置文件
        base_config_file = STORAGE_DIR / 'base_config.json'
        if not base_config_file.exists():
            default_base_config = {
                "baseUrl": "",
                "username": "",
                "password": ""
            }
            base_config_file.write_text(json.dumps(default_base_config, indent=2))
            logger.info("创建默认基础配置文件")
            
    except Exception as e:
        logger.error(f"初始化配置文件失败: {e}")


if __name__ == '__main__':
    init_config_files()
    # 创建事件循环来运行异步初始化
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_scheduler())
    uvicorn.run(
        "alist-sync-web:app",
        host="0.0.0.0",
        port=52441,
        reload=False,
        workers=1
    )
