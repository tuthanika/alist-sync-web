import os
import json
import time
import datetime
from pathlib import Path
from flask import current_app

class DataManager:
    """数据管理器，负责处理JSON文件的读写操作"""
    
    def __init__(self, data_dir=None):
        """初始化数据管理器"""
        self.data_dir = data_dir or "app/data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 定义数据文件路径
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.connections_file = os.path.join(self.data_dir, "connections.json")
        self.tasks_file = os.path.join(self.data_dir, "tasks.json")
        self.settings_file = os.path.join(self.data_dir, "settings.json")
        self.logs_file = os.path.join(self.data_dir, "logs.json")
        self.task_instances_file = os.path.join(self.data_dir, "task_instances.json")
        
        # 确保任务日志目录存在
        self.task_logs_dir = os.path.join(self.data_dir, "task_logs")
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
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write_json(self, file_path, data):
        """写入 JSON 文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, ensure_ascii=False, indent=2, fp=f)
    
    def format_timestamp(self, timestamp):
        """将时间戳格式化为 yyyy-MM-dd HH:mm:ss 格式"""
        if not timestamp:
            return ""
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
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
        logs = self._read_json(self.logs_file)
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
    
    def add_log(self, log_data):
        """添加日志"""
        logs = self._read_json(self.logs_file)
        timestamp = int(time.time())
        log_data["timestamp"] = timestamp
        log_data["timestamp_formatted"] = self.format_timestamp(timestamp)
        
        # 如果日志包含 task_id 但没有 task_name，尝试添加任务名称
        if "task_id" in log_data and "task_name" not in log_data:
            task = self.get_task(log_data["task_id"])
            if task:
                log_data["task_name"] = task.get("name", "未知任务")
        
        # 限制日志数量为最新的 1000 条
        logs.append(log_data)
        logs = sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:1000]
        
        self._write_json(self.logs_file, logs)
    
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
                if "baseUrl" in data and "token" in data:
                    # 这是alist_sync基本配置格式
                    format_type = "alist_sync_base_config"
                    result["details"]["format"] = format_type
                    result["details"]["detected_fields"] = ["baseUrl", "token"]
                    # 转换为标准格式
                    data = self._convert_alist_sync_base_config(data)
                elif "tasks" in data and isinstance(data["tasks"], list):
                    if data["tasks"] and all(isinstance(task, dict) and "syncDirs" in task for task in data["tasks"]):
                        # 这是alist_sync同步任务配置格式
                        format_type = "alist_sync_sync_config"
                        result["details"]["format"] = format_type
                        result["details"]["task_count"] = len(data["tasks"])
                        # 转换为标准格式
                        data = self._convert_alist_sync_sync_config(data)
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
        settings = self._read_json(self.settings_file)
        
        # 创建新的连接集合，完全覆盖现有连接
        connections = []
        
        # 生成连接ID映射表（存储路径到连接ID的映射）
        conn_path_to_id = {}
        next_conn_id = 1
            
        # 收集所有任务中使用的源存储和目标存储路径
        all_storage_paths = set()
        for sync_task in config.get("tasks", []):
            source_storage = sync_task.get("sourceStorage", "")
            if source_storage:
                all_storage_paths.add(source_storage)
            
            target_storages = sync_task.get("targetStorages", [])
            for target in target_storages:
                if target:
                    all_storage_paths.add(target)
        
        # 为每个存储路径创建一个新连接
        for storage_path in all_storage_paths:
            conn = {
                "connection_id": next_conn_id,
                "name": storage_path,
                "server": "",  # 这些字段需要用户稍后配置
                "username": "",
                "password": "",
                "token": "",
                "proxy": "",
                "max_retry": "3",
                "insecure": False,
                "status": "pending",  # 标记为待配置状态
                "created_at": self.format_timestamp(int(time.time())),
                "updated_at": self.format_timestamp(int(time.time()))
            }
            connections.append(conn)
            conn_path_to_id[storage_path] = next_conn_id
            next_conn_id += 1
            
        # 如果没有创建任何连接（没有存储路径），至少创建一个默认连接
        if not connections:
            connections.append({
                "connection_id": 1,
                "name": "default",
                "server": "",
                "username": "",
                "password": "",
                "token": "",
                "proxy": "",
                "max_retry": "3",
                "insecure": False,
                "status": "pending",
                "created_at": self.format_timestamp(int(time.time())),
                "updated_at": self.format_timestamp(int(time.time()))
            })
        
        # 创建新任务列表，每个任务都会获得一个新ID
        next_task_id = 1
        new_tasks = []
        
        for sync_task in config.get("tasks", []):
            # 获取源连接ID
            source_path = sync_task.get("sourceStorage", "")
            source_conn_id = conn_path_to_id.get(source_path, 1)  # 默认使用ID 1
            
            # 获取目标连接IDs
            target_paths = sync_task.get("targetStorages", [])
            target_conn_ids = [conn_path_to_id.get(path, 1) for path in target_paths if path]
            
            # 创建新的任务配置
            new_task = {
                "id": next_task_id,
                "name": sync_task.get("taskName", f"导入任务{next_task_id}"),
                "connection_id": 1,  # 默认使用第一个连接
                "enabled": True,
                "sync_type": "file_sync",
                "source_connection_id": source_conn_id,
                "source_connection_name": source_path,
                "source_path": sync_task.get("syncDirs", "").split(",")[0] if sync_task.get("syncDirs") else "",
                "target_connection_ids": target_conn_ids,
                "target_connection_names": ", ".join(target_paths),
                "target_path": "",  # alist_sync不同，目标位置在我们系统是自定义的
                "schedule": self._convert_cron_format(sync_task.get("cron", "")),
                "file_filter": sync_task.get("excludeDirs", ""),
                "created_at": self.format_timestamp(int(time.time())),
                "updated_at": self.format_timestamp(int(time.time())),
                "last_run": "",
                "next_run": "",
                "status": "pending"
            }
            
            new_tasks.append(new_task)
            next_task_id += 1
        
        return {
            "users": users,
            "connections": connections,
            "tasks": new_tasks,
            "settings": settings
        }
    
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