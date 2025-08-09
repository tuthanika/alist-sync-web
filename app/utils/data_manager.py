import os
import json
import time
import datetime
from datetime import datetime as dt, timedelta
import glob
import logging
from pathlib import Path
from flask import current_app

class DataManager:
    """数据管理器，负责处理JSON文件的读写操作"""
    
    def __init__(self, data_dir=None):
        """初始化数据管理器"""
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 设置数据目录
        self.data_dir = data_dir or os.path.join(project_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 设置配置文件目录
        self.config_dir = os.path.join(self.data_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 设置日志目录
        self.log_dir = os.path.join(self.data_dir, "log")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 定义数据文件路径
        self.users_file = os.path.join(self.config_dir, "users.json")
        self.connections_file = os.path.join(self.config_dir, "connections.json")
        self.tasks_file = os.path.join(self.config_dir, "tasks.json")
        self.settings_file = os.path.join(self.config_dir, "settings.json")
        self.logs_file = os.path.join(self.log_dir, "logs.json")
        self.task_instances_file = os.path.join(self.config_dir, "task_instances.json")
        
        # 确保任务日志目录存在
        self.task_logs_dir = os.path.join(self.log_dir, "task_logs")
        os.makedirs(self.task_logs_dir, exist_ok=True)
        
        # 创建初始数据文件（如果不存在）
        self._ensure_file_exists(self.users_file, self._get_default_users())
        self._ensure_file_exists(self.connections_file, [])
        self._ensure_file_exists(self.tasks_file, [])
        self._ensure_file_exists(self.settings_file, self._get_default_settings())
        self._ensure_file_exists(self.logs_file, [])
        self._ensure_file_exists(self.task_instances_file, [])
    
    def _get_default_settings(self):
        """获取默认设置"""
        return {
            "theme": "dark",
            "language": "zh_CN",
            "refresh_interval": 60,
            "keep_log_days": 7,  # 默认保留日志天数为7天
            "max_concurrent_tasks": 3,
            "default_retry_count": 3,
            "default_block_size": 10485760,  # 10MB
            "bandwidth_limit": 0,
            "log_level": "INFO",
            "debug_mode": False,
            "enable_webhook": False,
            "notification_type": "webhook",
            "webhook_url": "",
            "dingtalk_secret": "",
            "bark_sound": "default",
            "telegram_bot_token": "",
            "telegram_chat_id": ""
        }
    
    def _ensure_file_exists(self, file_path, default_data):
        """确保文件存在，如果不存在则创建"""
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, ensure_ascii=False, indent=2, fp=f)
                
    def _get_default_users(self):
        """获取默认用户"""
        return [
            {
                "id": 1,
                "username": "admin",
                "password": "admin",
                "created_at": self.format_timestamp(int(time.time())),
                "last_login": ""
            }
        ]
    
    def _read_json(self, file_path):
        """读取 JSON 文件"""
        try:
            # 如果文件不存在，创建默认内容
            if not os.path.exists(file_path):
                print(f"文件不存在，创建默认内容: {file_path}")
                if "logs.json" in file_path:
                    self._ensure_file_exists(file_path, [])
                elif "users.json" in file_path:
                    self._ensure_file_exists(file_path, self._get_default_users())
                elif "settings.json" in file_path:
                    self._ensure_file_exists(file_path, self._get_default_settings())
                else:
                    self._ensure_file_exists(file_path, [])
            
            # 尝试读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
                # 检查文件是否为空
                if not content:
                    print(f"文件为空: {file_path}")
                    if "logs.json" in file_path:
                        return []
                    elif "users.json" in file_path:
                        return self._get_default_users()
                    elif "settings.json" in file_path:
                        return self._get_default_settings()
                    else:
                        return []
                
                # 尝试解析JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误 ({file_path}): {str(e)}")
                    # 如果文件内容不是有效的JSON，返回默认值
                    if "logs.json" in file_path:
                        self._write_json(file_path, [])
                        return []
                    elif "users.json" in file_path:
                        default_users = self._get_default_users()
                        self._write_json(file_path, default_users)
                        return default_users
                    elif "settings.json" in file_path:
                        default_settings = self._get_default_settings()
                        self._write_json(file_path, default_settings)
                        return default_settings
                    else:
                        self._write_json(file_path, [])
                        return []
                        
        except Exception as e:
            print(f"读取JSON文件时出错 ({file_path}): {str(e)}")
            # 返回默认值
            if "logs.json" in file_path:
                return []
            elif "users.json" in file_path:
                return self._get_default_users()
            elif "settings.json" in file_path:
                return self._get_default_settings()
            else:
                return []
    
    def _write_json(self, file_path, data):
        """写入 JSON 文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 先写入临时文件
            temp_file = file_path + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, ensure_ascii=False, indent=2, fp=f)
            
            # 然后原子性地重命名为目标文件
            if os.path.exists(file_path):
                # 在Windows上需要先删除现有文件
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"删除现有文件失败: {str(e)}")
                    
            os.rename(temp_file, file_path)
        except Exception as e:
            print(f"写入JSON文件时出错 ({file_path}): {str(e)}")
            # 如果重命名失败，尝试直接写入
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, ensure_ascii=False, indent=2, fp=f)
            except Exception as write_error:
                print(f"直接写入也失败了: {str(write_error)}")
    
    def format_timestamp(self, timestamp):
        """将时间戳格式化为 yyyy-MM-dd HH:mm:ss 格式"""
        if not timestamp:
            return ""
        return dt.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    # 用户管理
    def get_users(self):
        """获取所有用户"""
        return self._read_json(self.users_file)
    
    def get_user(self, username):
        """通过用户名获取用户"""
        users = self.get_users()
        for user in users:
            if user["username"] == username:
                return user
        return None
    
    def authenticate_user(self, username, password):
        """验证用户名和密码"""
        user = self.get_user(username)
        if user and user["password"] == password:
            # 更新最后登录时间
            self.update_last_login(username)
            return user
        return None
    
    def update_user_password(self, username, new_password):
        """更新用户密码"""
        users = self.get_users()
        for i, user in enumerate(users):
            if user["username"] == username:
                users[i]["password"] = new_password
                users[i]["updated_at"] = self.format_timestamp(int(time.time()))
                self._write_json(self.users_file, users)
                return True
        return False
    
    def update_username(self, old_username, new_username):
        """更新用户名"""
        if self.get_user(new_username):
            return False  # 新用户名已存在
            
        users = self.get_users()
        for i, user in enumerate(users):
            if user["username"] == old_username:
                users[i]["username"] = new_username
                users[i]["updated_at"] = self.format_timestamp(int(time.time()))
                self._write_json(self.users_file, users)
                return True
        return False
    
    def update_last_login(self, username):
        """更新用户最后登录时间"""
        users = self.get_users()
        for i, user in enumerate(users):
            if user["username"] == username:
                users[i]["last_login"] = self.format_timestamp(int(time.time()))
                self._write_json(self.users_file, users)
                return True
        return False
    
    # 连接管理
    def get_connections(self):
        """获取所有连接"""
        return self._read_json(self.connections_file)
    
    def get_connection(self, conn_id):
        """获取单个连接"""
        connections = self.get_connections()
        for conn in connections:
            if conn["connection_id"] == conn_id:
                return conn
        return None
    
    def add_connection(self, connection_data):
        """添加连接"""
        connections = self.get_connections()
        # 生成新ID
        next_id = 1
        if connections:
            next_id = max(conn["connection_id"] for conn in connections) + 1
        
        connection_data["connection_id"] = next_id
        connection_data["created_at"] = self.format_timestamp(int(time.time()))
        connection_data["updated_at"] = self.format_timestamp(int(time.time()))
        
        connections.append(connection_data)
        self._write_json(self.connections_file, connections)
        return next_id
    
    def update_connection(self, conn_id, connection_data):
        """更新连接"""
        connections = self.get_connections()
        for i, conn in enumerate(connections):
            if conn["connection_id"] == conn_id:
                connection_data["connection_id"] = conn_id
                connection_data["created_at"] = conn.get("created_at")
                connection_data["updated_at"] = self.format_timestamp(int(time.time()))
                connections[i] = connection_data
                self._write_json(self.connections_file, connections)
                return True
        return False
    
    def delete_connection(self, conn_id):
        """删除连接"""
        connections = self.get_connections()
        connections = [conn for conn in connections if conn["connection_id"] != conn_id]
        self._write_json(self.connections_file, connections)
    
    # 任务管理
    def get_tasks(self):
        """获取所有任务"""
        return self._read_json(self.tasks_file)
    
    def get_task(self, task_id):
        """获取单个任务"""
        tasks = self.get_tasks()
        for task in tasks:
            if task["id"] == task_id:
                return task
        return None
    
    def add_task(self, task_data):
        """添加任务"""
        tasks = self.get_tasks()
        # 生成新ID
        next_id = 1
        if tasks:
            next_id = max(task["id"] for task in tasks) + 1
        
        task_data["id"] = next_id
        task_data["created_at"] = self.format_timestamp(int(time.time()))
        task_data["updated_at"] = self.format_timestamp(int(time.time()))
        task_data["status"] = "pending"
        task_data["last_run"] = ""
        task_data["next_run"] = ""
        
        tasks.append(task_data)
        self._write_json(self.tasks_file, tasks)
        return next_id
    
    def update_task(self, task_id, task_data):
        """更新任务"""
        tasks = self.get_tasks()
        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                task_data["id"] = task_id
                task_data["created_at"] = task.get("created_at")
                task_data["updated_at"] = self.format_timestamp(int(time.time()))
                # 保留其他状态字段
                for field in ["status", "last_run", "next_run"]:
                    if field in task and field not in task_data:
                        task_data[field] = task[field]
                
                tasks[i] = task_data
                self._write_json(self.tasks_file, tasks)
                return True
        return False
    
    def delete_task(self, task_id):
        """删除任务"""
        tasks = self.get_tasks()
        tasks = [task for task in tasks if task["id"] != task_id]
        self._write_json(self.tasks_file, tasks)
    
    def update_task_status(self, task_id, status, last_run=None, next_run=None):
        """更新任务状态"""
        tasks = self.get_tasks()
        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                task["status"] = status
                if last_run:
                    task["last_run"] = self.format_timestamp(last_run)
                if next_run:
                    # 如果提供的是数字时间戳，则格式化为字符串
                    task["next_run"] = self.format_timestamp(next_run)
                    current_app.logger.debug(f"已更新任务 {task_id} 的下次运行时间: {task['next_run']}")
                tasks[i] = task
                self._write_json(self.tasks_file, tasks)
                return True
        return False
    
    # 设置管理
    def get_settings(self):
        """获取设置"""
        return self._read_json(self.settings_file)
    
    def update_settings(self, settings_data):
        """更新设置"""
        current_settings = self.get_settings()
        current_settings.update(settings_data)
        self._write_json(self.settings_file, current_settings)
    
    # 日志管理
    def get_logs(self, limit=100):
        """获取最新日志"""
        try:
            logs = self._read_json(self.logs_file)
            
            # 确保logs是一个列表
            if not isinstance(logs, list):
                print(f"日志文件内容不是有效的列表，重置为空列表")
                logs = []
                self._write_json(self.logs_file, logs)
                
            logs_sorted = sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]
            
            # 格式化时间戳和添加缺失的任务名称
            for log in logs_sorted:
                if "timestamp" in log:
                    log["timestamp_formatted"] = self.format_timestamp(log["timestamp"])
                
                # 确保所有包含 task_id 的日志都有 task_name
                if "task_id" in log and (not log.get("task_name") or log.get("task_name") == ""):
                    task = self.get_task(log["task_id"])
                    if task:
                        log["task_name"] = task.get("name", f"任务 {log['task_id']}")
                    else:
                        # 如果找不到对应的任务，使用任务ID作为备用显示
                        log["task_name"] = f"任务 {log['task_id']}"
            
            return logs_sorted
            
        except Exception as e:
            print(f"获取日志时出错: {str(e)}")
            # 如果出错，返回空列表
            return []
    
    def add_log(self, log_data):
        """添加日志"""
        try:
            logs = self._read_json(self.logs_file)
            timestamp = int(time.time())
            log_data["timestamp"] = timestamp
            log_data["timestamp_formatted"] = self.format_timestamp(timestamp)
            
            # 如果日志包含 task_id 但没有 task_name，尝试添加任务名称
            if "task_id" in log_data and "task_name" not in log_data:
                task = self.get_task(log_data["task_id"])
                if task:
                    log_data["task_name"] = task.get("name", "未知任务")
            
            # 确保logs是一个列表
            if not isinstance(logs, list):
                logs = []
                
            # 限制日志数量为最新的 1000 条
            logs.append(log_data)
            logs = sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:1000]
            
            # 写入日志前打印调试信息
            print(f"正在写入日志，当前日志条数: {len(logs)}")
            try:
                self._write_json(self.logs_file, logs)
                print(f"日志写入成功 - {log_data.get('message', '无消息')}")
            except Exception as e:
                print(f"写入日志时发生错误: {str(e)}")
                # 尝试重新创建日志文件
                with open(self.logs_file, 'w', encoding='utf-8') as f:
                    json.dump(logs, ensure_ascii=False, indent=2, fp=f)
        except Exception as e:
            print(f"添加日志失败: {str(e)}")
            # 确保日志文件存在并有效
            self._ensure_file_exists(self.logs_file, [])
    
    def clear_old_logs(self, days=None):
        """清理旧日志"""
        if days is None:
            settings = self.get_settings()
            days = settings.get("keep_log_days", 7)
        
        logs = self._read_json(self.logs_file)
        current_time = int(time.time())
        cutoff_time = current_time - (days * 86400)  # 一天有 86400 秒
        
        logs = [log for log in logs if log.get("timestamp", 0) > cutoff_time]
        self._write_json(self.logs_file, logs)
    
    # 任务实例管理
    def get_task_instances(self, task_id=None, limit=50):
        """获取任务实例列表，可以按任务ID筛选"""
        instances = self._read_json(self.task_instances_file)
        
        # 按时间戳降序排序
        instances = sorted(instances, key=lambda x: x.get("start_time", 0), reverse=True)
        
        # 如果指定了任务ID，则只返回该任务的实例
        if task_id:
            instances = [inst for inst in instances if inst.get("task_id") == task_id]
        
        # 返回指定数量的实例
        return instances[:limit]
    
    def get_task_instance(self, instance_id):
        """获取单个任务实例"""
        instances = self._read_json(self.task_instances_file)
        for instance in instances:
            if instance.get("task_instances_id") == instance_id:
                return instance
        return None
    
    def add_task_instance(self, task_id, start_params=None):
        """添加新的任务实例记录"""
        instances = self._read_json(self.task_instances_file)
        task = self.get_task(task_id)
        
        if not task:
            return None
        
        # 生成新ID
        next_id = 1
        if instances:
            next_id = max(instance.get("task_instances_id", 0) for instance in instances) + 1
        
        # 获取当前时间戳
        start_time = int(time.time())
        
        # 创建任务实例记录
        instance = {
            "task_instances_id": next_id,
            "task_id": task_id,
            "task_name": task.get("name", f"任务 {task_id}"),
            "start_time": start_time,
            "start_time_formatted": self.format_timestamp(start_time),
            "end_time": 0,
            "end_time_formatted": "",
            "status": "running",
            "params": start_params or {},
            "result": {}
        }
        
        instances.append(instance)
        self._write_json(self.task_instances_file, instances)
        
        # 创建任务日志文件
        self._create_task_log_file(task_id, instance["task_instances_id"], f"开始执行任务: {instance['task_name']}")
        
        return instance
    
    def update_task_instance(self, instance_id, status, result=None, end_time=None):
        """更新任务实例状态"""
        instances = self._read_json(self.task_instances_file)
        
        for i, instance in enumerate(instances):
            if instance.get("task_instances_id") == instance_id:
                instances[i]["status"] = status
                
                if result:
                    instances[i]["result"] = result
                
                if end_time or status in ["completed", "failed"]:
                    end_time = end_time or int(time.time())
                    instances[i]["end_time"] = end_time
                    instances[i]["end_time_formatted"] = self.format_timestamp(end_time)
                
                self._write_json(self.task_instances_file, instances)
                
                # 更新任务日志
                self._append_task_log(
                    instance.get("task_id"), 
                    instance_id, 
                    f"任务状态更新为: {status}" + (f", 结果: {json.dumps(result, ensure_ascii=False)}" if result else "")
                )
                
                return True
                
        return False
    
    def clear_old_task_instances(self, days=None):
        """清理旧的任务实例记录"""
        if days is None:
            settings = self.get_settings()
            days = settings.get("keep_log_days", 7)
        
        instances = self._read_json(self.task_instances_file)
        current_time = int(time.time())
        cutoff_time = current_time - (days * 86400)  # 一天有 86400 秒
        
        # 保留较新的任务实例
        new_instances = [inst for inst in instances if inst.get("start_time", 0) > cutoff_time]
        
        # 删除旧实例对应的日志文件
        old_instances = [inst for inst in instances if inst.get("start_time", 0) <= cutoff_time]
        for instance in old_instances:
            log_file = self._get_task_log_file_path(instance.get("task_id"), instance.get("task_instances_id"))
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except:
                    pass
        
        self._write_json(self.task_instances_file, new_instances)
    
    def clear_main_log_files(self, days=None):
        """清理主日志文件alist_sync.log的历史备份
        每天轮换的日志文件格式为 alist_sync.log.YYYY-MM-DD
        """
        if days is None:
            settings = self.get_settings()
            days = settings.get("keep_log_days", 7)
        
        # 计算截止日期
        cutoff_date = dt.now() - timedelta(days=days)
        
        # 获取所有日志文件
        log_files = glob.glob(os.path.join(self.log_dir, "alist_sync.log.*"))
        
        # 遍历所有日志文件
        for log_file in log_files:
            try:
                # 提取日期部分
                file_name = os.path.basename(log_file)
                date_part = file_name.split('.')[-1]  # 获取日期部分 YYYY-MM-DD
                
                # 解析日期
                file_date = dt.strptime(date_part, "%Y-%m-%d")
                
                # 如果日期早于保留期限，则删除
                if file_date < cutoff_date:
                    os.remove(log_file)
                    logging.info(f"已删除过期日志文件: {file_name}")
            except Exception as e:
                logging.error(f"处理日志文件 {log_file} 时出错: {str(e)}")
    
    # 任务日志管理
    def _get_task_log_file_path(self, task_id, instance_id):
        """获取任务日志文件路径"""
        return os.path.join(self.task_logs_dir, f"task_{task_id}_instance_{instance_id}.log")
    
    def _create_task_log_file(self, task_id, instance_id, initial_message=None):
        """创建任务日志文件"""
        log_file = self._get_task_log_file_path(task_id, instance_id)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            timestamp = self.format_timestamp(int(time.time()))
            f.write(f"[{timestamp}] 任务实例启动\n")
            
            if initial_message:
                f.write(f"[{timestamp}] {initial_message}\n")
    
    def _append_task_log(self, task_id, instance_id, message):
        """向任务日志文件追加内容"""
        log_file = self._get_task_log_file_path(task_id, instance_id)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = self.format_timestamp(int(time.time()))
            f.write(f"[{timestamp}] {message}\n")
    
    def get_task_log(self, task_id, instance_id):
        """获取任务日志内容"""
        log_file = self._get_task_log_file_path(task_id, instance_id)
        
        if not os.path.exists(log_file):
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            
        # 将日志文本转换为列表
        log_lines = log_content.split('\n')
        return [line for line in log_lines if line.strip()]
    
    # 导入导出功能
    def export_data(self):
        """导出所有数据为一个字典"""
        export_data = {
            "users": self._read_json(self.users_file),
            "connections": self._read_json(self.connections_file),
            "tasks": self._read_json(self.tasks_file),
            "settings": self._read_json(self.settings_file)
        }
        return export_data
    
    def import_data(self, data, backup=True):
        """导入数据并覆盖现有数据，可选备份原数据
        
        Args:
            data (dict): 包含要导入的数据的字典
            backup (bool): 是否备份原数据，默认为True
            
        Returns:
            dict: 包含导入结果的字典
        """
        result = {"success": True, "message": "数据导入成功", "details": {}}
        backup_files = {}
        
        try:
            # 检查数据格式，确定是标准格式还是alist_sync格式
            format_type = "unknown"
            
            if isinstance(data, dict):
                # 检测旧版基本配置格式
                if "baseUrl" in data and "token" in data:
                    # 这是alist_sync基本配置格式
                    format_type = "alist_sync_base_config"
                    result["details"]["format"] = format_type
                    result["details"]["detected_fields"] = ["baseUrl", "token"]
                    # 转换为标准格式
                    data = self._convert_alist_sync_base_config(data)
                
                # 检测旧版同步任务配置格式(两种可能的格式)
                elif "tasks" in data and isinstance(data["tasks"], list):
                    # 检查是旧版格式还是新版格式
                    if data["tasks"] and all(isinstance(task, dict) for task in data["tasks"]):
                        old_format = any("->" in task.get("syncDirs", "") for task in data["tasks"] if "syncDirs" in task)
                        new_format = any(all(key in task for key in ["sourceStorage", "targetStorages", "syncDirs"]) 
                                        for task in data["tasks"])
                        
                        if old_format or new_format:
                            # 这是alist_sync同步任务配置格式
                            format_type = "alist_sync_sync_config"
                            result["details"]["format"] = format_type
                            result["details"]["task_count"] = len(data["tasks"])
                            
                            # 标记配置版本
                            if new_format:
                                result["details"]["format_version"] = "新版格式"
                            else:
                                result["details"]["format_version"] = "旧版格式"
                            
                            # 转换为标准格式
                            data = self._convert_alist_sync_sync_config(data)
                        else:
                            # 检查是否是标准格式
                            if all(key in data for key in ["users", "connections", "tasks", "settings"]):
                                format_type = "standard"
                                result["details"]["format"] = format_type
                            else:
                                # 无法识别的格式
                                raise ValueError("无法识别的任务数据格式，缺少必要字段")
                    else:
                        # 可能是标准格式或无效格式
                        if all(key in data for key in ["users", "connections", "tasks", "settings"]):
                            format_type = "standard"
                            result["details"]["format"] = format_type
                        else:
                            # 无法识别的格式
                            raise ValueError("无法识别的数据格式，缺少必要字段")
                else:
                    # 可能是标准格式
                    if all(key in data for key in ["users", "connections", "tasks", "settings"]):
                        format_type = "standard"
                        result["details"]["format"] = format_type
                    else:
                        # 无法识别的格式
                        missing_keys = [k for k in ["users", "connections", "tasks", "settings"] if k not in data]
                        raise ValueError(f"数据格式无效，缺少必要字段: {', '.join(missing_keys)}")
            else:
                raise ValueError("导入数据必须是有效的JSON对象")
            
            # 先进行备份
            if backup:
                timestamp = int(time.time())
                backup_dir = os.path.join(self.data_dir, f"backup_{timestamp}")
                os.makedirs(backup_dir, exist_ok=True)
                
                # 备份文件
                for file_name, json_file in [
                    ("users", self.users_file),
                    ("connections", self.connections_file),
                    ("tasks", self.tasks_file),
                    ("settings", self.settings_file)
                ]:
                    if os.path.exists(json_file):
                        backup_file = os.path.join(backup_dir, os.path.basename(json_file))
                        with open(json_file, 'r', encoding='utf-8') as src, \
                             open(backup_file, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                        backup_files[file_name] = backup_file
                
                result["details"]["backup_dir"] = backup_dir
                result["details"]["backup_files"] = backup_files
                result["details"]["backup_timestamp"] = self.format_timestamp(timestamp)
            
            # 处理导入数据
            for data_type, file_path in [
                ("users", self.users_file),
                ("connections", self.connections_file),
                ("tasks", self.tasks_file),
                ("settings", self.settings_file)
            ]:
                if data_type in data:
                    self._write_json(file_path, data[data_type])
                    if isinstance(data[data_type], list):
                        result["details"][data_type] = f"导入成功，共{len(data[data_type])}条记录"
                    else:
                        result["details"][data_type] = "导入成功"
                else:
                    result["details"][data_type] = "未提供数据，保持不变"
            
            # 添加额外的统计信息
            if format_type == "alist_sync_base_config":
                result["message"] = "成功导入AList-Sync基本配置，已更新连接信息"
            elif format_type == "alist_sync_sync_config":
                task_count = len(data.get("tasks", []))
                result["message"] = f"成功导入AList-Sync同步任务配置，共{task_count}个任务（已覆盖原有任务）"
            else:
                # 标准格式，添加统计信息
                result["message"] = "成功导入系统数据，已覆盖原有配置"
            
            return result
        except Exception as e:
            result["success"] = False
            result["message"] = f"导入失败: {str(e)}"
            # 如果导入失败，尝试恢复备份
            if backup and backup_files:
                try:
                    for data_type, backup_file in backup_files.items():
                        dest_file = getattr(self, f"{data_type}_file")
                        with open(backup_file, 'r', encoding='utf-8') as src, \
                             open(dest_file, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                    result["details"]["recovery"] = "已从备份恢复"
                except Exception as recovery_error:
                    result["details"]["recovery_error"] = str(recovery_error)
            return result
    
    def _convert_alist_sync_base_config(self, config):
        """将alist_sync基本配置转换为标准格式
        
        Args:
            config (dict): alist_sync基本配置
            
        Returns:
            dict: 标准格式的配置数据
        """
        # 读取现有数据作为基础
        users = self._read_json(self.users_file)
        tasks = self._read_json(self.tasks_file)
        settings = self._read_json(self.settings_file)
        
        # 创建新的连接数据，完全覆盖现有连接
        connections = [{
            "connection_id": 1,
            "name": "alist",
            "server": config.get("baseUrl", ""),
            "username": config.get("username", ""),
            "password": config.get("password", ""),
            "token": config.get("token", ""),
            "proxy": "",
            "max_retry": "3", 
            "insecure": False,
            "status": "online",
            "created_at": self.format_timestamp(int(time.time())),
            "updated_at": self.format_timestamp(int(time.time()))
        }]
        
        return {
            "users": users,
            "connections": connections,
            "tasks": tasks,
            "settings": settings
        }
    
    def _convert_alist_sync_sync_config(self, config):
        """将alist_sync同步任务配置转换为标准格式
        
        Args:
            config (dict): alist_sync同步任务配置
            
        Returns:
            dict: 标准格式的配置数据
        """
        # 读取现有数据作为基础
        users = self._read_json(self.users_file)
        connections = self._read_json(self.connections_file)
        settings = self._read_json(self.settings_file)
        
        # 获取所有存储路径（用于正确识别路径前缀）
        storage_paths = self._get_storage_paths()
        
        # 转换任务列表
        converted_tasks = []
        
        # 处理每个同步任务
        for i, sync_task in enumerate(config.get("tasks", [])):
            # 任务名称(如果没有则生成默认名称)
            task_name = sync_task.get("taskName") or f"同步任务 {i+1}"
            
            # 获取同步模式和差异项处理策略
            sync_mode = sync_task.get("syncMode", "data")
            sync_del_action = sync_task.get("syncDelAction", "none")
            
            # 映射旧格式同步模式到新格式
            sync_type = "file_sync"  # 默认为文件同步
            if sync_mode == "data" or sync_mode == "file":
                sync_type = "file_sync"
            elif sync_mode == "file_move":
                sync_type = "file_move"
            
            # 获取计划和文件过滤器
            schedule = self._convert_cron_format(sync_task.get("cron", ""))
            file_filter = sync_task.get("regexPatterns", "")
            exclude_dirs = sync_task.get("excludeDirs", "")
            
            # --------- 处理不同的路径格式 ---------
            
            # 检查是否是包含paths数组的格式
            if "paths" in sync_task and isinstance(sync_task["paths"], list):
                # 处理包含多个源目标路径对的任务
                for path_idx, path_item in enumerate(sync_task["paths"]):
                    # 处理常规路径对
                    src_path = None
                    dst_path = None
                    
                    # 检查是否是移动模式的路径对
                    if "srcPathMove" in path_item and "dstPathMove" in path_item:
                        src_path = path_item.get("srcPathMove", "").strip()
                        dst_path = path_item.get("dstPathMove", "").strip()
                    # 检查是否是常规路径对
                    elif "srcPath" in path_item and "dstPath" in path_item:
                        src_path = path_item.get("srcPath", "").strip()
                        dst_path = path_item.get("dstPath", "").strip()
                        
                    # 如果无法获取有效路径，跳过
                    if not src_path or not dst_path:
                        continue
                        
                    # 组装任务
                    path_task_name = f"{task_name} - 路径{path_idx+1}" if len(sync_task["paths"]) > 1 else task_name
                    
                    # 智能拆分源路径和目标路径
                    src_conn_id, src_real_path = self._split_path_with_storage_list(src_path, storage_paths)
                    dst_conn_id, dst_real_path = self._split_path_with_storage_list(dst_path, storage_paths)
                    
                    # 创建任务数据
                    task_data = {
                        "id": len(converted_tasks) + 1,  # 确保ID唯一
                        "name": path_task_name,
                        "connection_id": 1,  # 默认连接ID
                        "source_connection_id": src_conn_id,
                        "source_connection_name": src_conn_id,
                        "target_connection_ids": [dst_conn_id],
                        "target_connection_names": dst_conn_id,
                        "source_path": src_real_path,
                        "target_path": dst_real_path,
                        "sync_type": sync_type,
                        "sync_diff_action": sync_del_action,
                        "schedule": schedule,
                        "file_filter": file_filter,
                        "exclude_dirs": exclude_dirs,
                        "enabled": True,
                        "created_at": self.format_timestamp(int(time.time())),
                        "updated_at": self.format_timestamp(int(time.time())),
                        "last_run": "",
                        "next_run": "",
                        "status": "pending"
                    }
                    
                    converted_tasks.append(task_data)
                    
            # 处理旧格式: syncDirs包含"源目录->目标目录"格式
            elif "syncDirs" in sync_task and "->" in sync_task.get("syncDirs", ""):
                dirs = sync_task.get("syncDirs", "").strip()
                if not dirs:
                    continue
                    
                parts = dirs.split("->")
                if len(parts) != 2:
                    continue
                    
                source_dir = parts[0].strip()
                dst_dir = parts[1].strip()
                
                # 创建任务
                task_data = {
                    "id": len(converted_tasks) + 1,
                    "name": task_name,
                    "connection_id": 1,  # 默认连接ID
                    "source_connection_id": "",
                    "source_connection_name": "",
                    "target_connection_ids": [""],
                    "target_connection_names": "",
                    "source_path": source_dir,
                    "target_path": dst_dir,
                    "sync_type": sync_type,
                    "sync_diff_action": sync_del_action,
                    "schedule": schedule,
                    "file_filter": file_filter,
                    "exclude_dirs": exclude_dirs,
                    "enabled": True,
                    "created_at": self.format_timestamp(int(time.time())),
                    "updated_at": self.format_timestamp(int(time.time())),
                    "last_run": "",
                    "next_run": "",
                    "status": "pending"
                }
                
                converted_tasks.append(task_data)
                
            # 处理标准格式: 有sourceStorage和targetStorages
            elif "syncDirs" in sync_task and "sourceStorage" in sync_task and "targetStorages" in sync_task:
                source_storage = sync_task.get("sourceStorage", "").strip()
                sync_dirs = sync_task.get("syncDirs", "").strip()
                
                # 如果没有源存储或同步目录，跳过
                if not source_storage or not sync_dirs:
                    continue
                
                # 获取目标存储列表，忽略空值
                target_storages = [
                    storage for storage in sync_task.get("targetStorages", [])
                    if storage and storage.strip()
                ]
                
                # 如果没有目标存储，跳过
                if not target_storages:
                    continue
                
                # 创建单个任务包含所有目标存储
                # 格式化源路径
                source_path = sync_dirs
                
                # 创建任务数据
                task_data = {
                    "id": len(converted_tasks) + 1,  # 确保ID唯一
                    "name": task_name,
                    "connection_id": 1,  # 默认连接ID
                    "source_connection_id": source_storage,
                    "source_connection_name": source_storage,
                    "target_connection_ids": target_storages,
                    "target_connection_names": ",".join([ts.split('/')[-1] if '/' in ts else ts for ts in target_storages]),
                    "source_path": sync_dirs,
                    "target_path": sync_dirs,
                    "sync_type": sync_type,
                    "sync_diff_action": sync_del_action,
                    "schedule": schedule,
                    "file_filter": file_filter,
                    "exclude_dirs": exclude_dirs,
                    "enabled": True,
                    "created_at": self.format_timestamp(int(time.time())),
                    "updated_at": self.format_timestamp(int(time.time())),
                    "last_run": "",
                    "next_run": "",
                    "status": "pending"
                }
                
                converted_tasks.append(task_data)
        
        return {
            "users": users,
            "connections": connections,
            "tasks": converted_tasks,
            "settings": settings
        }
    
    def _get_storage_paths(self):
        """获取所有存储路径列表，用于智能拆分导入路径
        
        Returns:
            list: 存储路径列表，按照长度从长到短排序
        """
        # 从配置文件获取已保存的连接信息
        connections = self._read_json(self.connections_file)
        if not connections:
            return []
            
        # 收集所有可能的存储路径
        all_storage_paths = []
        
        # 从连接中获取存储路径
        from app.alist_sync import AlistSync
        for conn in connections:
            try:
                # 创建AlistSync实例
                alist = AlistSync(
                    conn.get('server'),
                    conn.get('username'),
                    conn.get('password'),
                    conn.get('token')
                )
                
                # 尝试登录
                if alist.login():
                    # 获取存储列表
                    storage_list = alist.get_storage_list()
                    if isinstance(storage_list, list):
                        all_storage_paths.extend(storage_list)
                
                # 关闭连接
                alist.close()
            except Exception as e:
                # 忽略连接错误，继续处理其他连接
                continue
        
        # 删除重复项
        all_storage_paths = list(set(all_storage_paths))
        
        # 按长度从长到短排序，以确保匹配最具体的路径
        all_storage_paths.sort(key=len, reverse=True)
        
        return all_storage_paths
        
    def _split_path_with_storage_list(self, full_path, storage_paths):
        """使用存储路径列表智能拆分完整路径
        
        Args:
            full_path (str): 完整路径
            storage_paths (list): 存储路径列表
            
        Returns:
            tuple: (存储路径, 实际路径)
        """
        # 默认使用简单拆分方式（/dav/xxx/）
        # 先尝试匹配存储路径
        if storage_paths:
            for storage in storage_paths:
                if full_path.startswith(storage):
                    # 找到匹配的存储路径
                    real_path = full_path[len(storage):] if full_path.startswith(storage) else full_path
                    # 确保实际路径前面有斜杠
                    if not real_path.startswith('/'):
                        real_path = '/' + real_path
                    return storage, real_path
        
        # 如果没有匹配到存储路径，使用默认的拆分方式
        parts = full_path.split('/', 2)
        if len(parts) >= 3:  # 格式应该是 /dav/xxx/actual_path
            storage_path = f"/{parts[1]}/{parts[2]}" if parts[1] and parts[2] else ""
            actual_path = f"/{parts[3]}" if len(parts) > 3 and parts[3] else "/"
            return storage_path, actual_path
        
        # 无法拆分，返回整个路径作为存储路径，根目录作为实际路径
        return full_path, "/"
    
    def _convert_cron_format(self, cron_str):
        """转换cron表达式格式，确保兼容性
        
        Args:
            cron_str (str): 原始cron表达式
            
        Returns:
            str: 转换后的cron表达式
        """
        if not cron_str:
            return ""
            
        # alist_sync通常使用标准cron表达式，可以直接使用
        return cron_str 