import time
import threading
import requests
import os
import json
import hashlib
from flask import current_app
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
import logging
import traceback
from app.utils.notifier import Notifier

class SyncManager:
    """同步管理器，负责执行同步任务"""
    
    def __init__(self):
        # 初始化带有时区的调度器
        self.scheduler = BackgroundScheduler(timezone=timezone('Asia/Shanghai'))
        self.scheduler.start()
        self.running_tasks = {}
        self.lock = threading.Lock()
        self.is_initialized = False
        self.notifier = Notifier()
    
    def initialize_scheduler(self):
        """初始化调度器，加载所有任务"""
        if self.is_initialized:
            current_app.logger.info("调度器已经初始化，跳过")
            return
            
        current_app.logger.info("开始初始化任务调度器...")
        
        try:
            data_manager = current_app.config['DATA_MANAGER']
            tasks = data_manager.get_tasks()
            
            # 移除所有现有任务
            for job in self.scheduler.get_jobs():
                self.scheduler.remove_job(job.id)
                current_app.logger.debug(f"移除旧任务: {job.id}")
            
            task_count = 0
            for task in tasks:
                if task.get("enabled", True) and task.get("schedule"):
                    # 检查任务是否处于启用状态且有调度计划
                    try:
                        self.schedule_task(task)
                        task_count += 1
                    except Exception as e:
                        current_app.logger.error(f"添加任务 {task.get('name', task.get('id'))} 失败: {str(e)}")
                    
            current_app.logger.info(f"已加载 {task_count} 个定时任务到调度器")
            
            # 更新所有任务的下次运行时间
            self._update_all_next_run_times()
            
            # 输出当前所有已计划任务
            jobs = self.scheduler.get_jobs()
            current_app.logger.info(f"调度器中共有 {len(jobs)} 个任务")
            for job in jobs:
                current_app.logger.info(f"已计划任务: {job.id}, 调度: {job.trigger}, 下次运行时间: {job.next_run_time}")
            
            # 标记初始化完成
            self.is_initialized = True
            
        except Exception as e:
            current_app.logger.error(f"初始化调度器失败: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            
    def _update_all_next_run_times(self):
        """更新所有任务的下次运行时间"""
        try:
            data_manager = current_app.config['DATA_MANAGER']
            jobs = self.scheduler.get_jobs()
            updated_count = 0
            
            current_app.logger.info(f"正在更新 {len(jobs)} 个任务的下次运行时间")
            
            for job in jobs:
                # 从job ID中提取任务ID
                if job.id.startswith('task_'):
                    task_id = int(job.id.replace('task_', ''))
                    
                    # 获取任务
                    task = data_manager.get_task(task_id)
                    if task and job.next_run_time:
                        # 更新任务的下次运行时间
                        next_run_timestamp = int(job.next_run_time.timestamp())
                        data_manager.update_task_status(task_id, task.get("status", "pending"), next_run=next_run_timestamp)
                        updated_count += 1
                        current_app.logger.debug(f"已更新任务 {task_id} 的下次运行时间: {job.next_run_time}")
            
            current_app.logger.info(f"已成功更新 {updated_count} 个任务的下次运行时间")
            return updated_count
            
        except Exception as e:
            current_app.logger.error(f"更新任务的下次运行时间失败: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            return 0
    
    def schedule_task(self, task):
        """添加任务到调度器"""
        task_id = task["id"]
        schedule = task.get("schedule")
        
        if not schedule or not schedule.strip():
            current_app.logger.warning(f"任务 {task_id} 没有有效的调度计划，跳过")
            return
        
        # 从调度器中移除已有任务（如果存在）
        job_id = f"task_{task_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            current_app.logger.debug(f"已移除现有任务: {job_id}")
        
        try:
            # 解析cron表达式
            cron_parts = self._parse_cron_expression(schedule)
            
            # 添加新任务
            job = self.scheduler.add_job(
                self.run_task,
                'cron',
                id=job_id,
                args=[task_id],
                **cron_parts,
                replace_existing=True,
                misfire_grace_time=3600  # 允许1小时的错过执行宽限期
            )
            
            # 记录调度信息
            cron_readable = f"{cron_parts.get('minute')} {cron_parts.get('hour')} {cron_parts.get('day')} {cron_parts.get('month')} {cron_parts.get('day_of_week')}"
            current_app.logger.info(f"已添加任务 {job_id}({task.get('name')}) 到调度器，调度: {cron_readable}, 下次运行: {job.next_run_time}")
            
            # 更新任务的下次运行时间
            try:
                if hasattr(current_app, 'config') and 'DATA_MANAGER' in current_app.config:
                    data_manager = current_app.config['DATA_MANAGER']
                    if job.next_run_time:
                        next_run_timestamp = int(job.next_run_time.timestamp())
                        data_manager.update_task_status(task_id, task.get("status", "pending"), next_run=next_run_timestamp)
                        current_app.logger.debug(f"已更新任务 {task_id} 的下次运行时间: {job.next_run_time}")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                current_app.logger.error(f"更新任务 {task_id} 的下次运行时间失败: {str(e)}")
                current_app.logger.error(f"详细错误: {error_details}")
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            current_app.logger.error(f"添加任务 {task_id} 到调度器失败: {str(e)}")
            current_app.logger.error(f"详细错误: {error_details}")
    
    def _parse_cron_expression(self, cron_expr):
        """解析 cron 表达式"""
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"无效的 cron 表达式: {cron_expr}，应为5个部分")
        
        # 记录解析结果
        result = {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'day_of_week': parts[4]
        }
        current_app.logger.debug(f"解析 cron 表达式: {cron_expr} -> {result}")
        return result
    
    def run_task(self, task_id):
        """运行同步任务"""
        # 获取Flask应用实例
        from flask import current_app, Flask
        
        # 如果当前没有应用上下文，尝试创建一个
        app = None
        app_context = None
        
        try:
            # 尝试获取当前应用
            app = current_app._get_current_object()
        except RuntimeError:
            # 如果没有当前应用上下文，尝试从配置中获取
            try:
                # 尝试使用全局应用实例
                from app import flask_app
                if flask_app:
                    app = flask_app
                    app_context = app.app_context()
                    app_context.push()
                    print(f"使用全局应用实例为任务 {task_id} 创建上下文")
                else:
                    # 如果没有全局应用实例，创建一个新的
                    from app import create_app
                    app = create_app()
                    app_context = app.app_context()
                    app_context.push()
                    print(f"为任务 {task_id} 创建了新的应用上下文")
            except Exception as e:
                print(f"创建应用上下文失败: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return {"status": "error", "message": f"无法创建应用上下文: {str(e)}"}
        
        try:
            # 获取数据管理器
            data_manager = app.config['DATA_MANAGER']
            task = data_manager.get_task(task_id)
            
            if not task:
                return {"status": "error", "message": "任务不存在"}
            
            # 检查任务是否正在运行
            with self.lock:
                if task_id in self.running_tasks:
                    return {"status": "error", "message": "任务已在运行中"}
                self.running_tasks[task_id] = time.time()
            
            try:
                # 创建任务实例记录
                task_instance = data_manager.add_task_instance(task_id, {
                    "sync_type": task.get("sync_type", "file_sync"),
                    "source_path": task.get("source_path", "/"),
                    "target_path": task.get("target_path", "/")
                })
                
                instance_id = task_instance["task_instances_id"]
                
                # 更新任务状态
                current_time = int(time.time())
                data_manager.update_task_status(task_id, "running", last_run=current_time)
                
                # 记录开始日志
                data_manager.add_log({
                    "task_id": task_id,
                    "instance_id": instance_id,
                    "level": "INFO",
                    "message": f"开始执行任务: {task.get('name', f'任务 {task_id}')}",
                    "details": {"instance_id": instance_id}
                })
                
                # 记录实例日志
                data_manager._append_task_log(task_id, instance_id, "准备执行任务")
                
                # 执行同步操作
                result = self._execute_task_with_alist_sync(task, task_id, instance_id)
                
                # 更新任务状态
                status = "completed" if result.get("status") == "success" else "failed"
                data_manager.update_task_status(task_id, status, last_run=current_time)
                
                # 更新任务实例状态
                data_manager.update_task_instance(instance_id, status, result)
                
                # 记录完成日志
                data_manager.add_log({
                    "task_id": task_id,
                    "instance_id": instance_id,
                    "level": "INFO" if status == "completed" else "ERROR",
                    "message": f"任务执行{('成功' if status == 'completed' else '失败')}: {task.get('name', f'任务 {task_id}')}",
                    "details": result
                })
                
                # 记录实例日志
                data_manager._append_task_log(
                    task_id, 
                    instance_id, 
                    f"任务执行{('成功' if status == 'completed' else '失败')}: {json.dumps(result, ensure_ascii=False)}"
                )
                
                # 发送通知
                task_duration = int(time.time()) - current_time
                notification_title = f"任务执行{'成功' if status == 'completed' else '失败'}"
                notification_content = result.get("message", "")
                
                # 添加任务信息
                task_info = {
                    "id": task_id,
                    "name": task.get('name', f'任务 {task_id}'),
                    "status": status,
                    "duration": f"{task_duration}秒",
                    "instance_id": instance_id
                }
                
                # 发送通知
                self.notifier.send_notification(notification_title, notification_content, task_info)
                
                return {
                    "status": "success",
                    "message": "任务已完成执行", 
                    "instance_id": instance_id,
                    "result": result
                }
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                
                # 发生异常，更新任务状态为失败
                data_manager.update_task_status(task_id, "failed", last_run=int(time.time()))
                
                # 如果已创建实例，更新实例状态
                if 'instance_id' in locals():
                    error_result = {"status": "error", "message": str(e)}
                    data_manager.update_task_instance(instance_id, "failed", error_result)
                    data_manager._append_task_log(task_id, instance_id, f"任务执行异常: {str(e)}\n{error_details}")
                
                # 记录错误日志
                data_manager.add_log({
                    "task_id": task_id,
                    "level": "ERROR",
                    "message": f"任务执行异常: {task.get('name', f'任务 {task_id}')}",
                    "details": {"error": str(e)}
                })
                
                # 发送通知
                task_duration = 0
                if 'current_time' in locals():
                    task_duration = int(time.time()) - current_time
                    
                notification_title = f"任务执行失败"
                notification_content = f"执行出错: {str(e)}"
                
                # 添加任务信息
                task_info = {
                    "id": task_id,
                    "name": task.get('name', f'任务 {task_id}'),
                    "status": "failed",
                    "duration": f"{task_duration}秒",
                    "instance_id": instance_id if 'instance_id' in locals() else None
                }
                
                # 发送通知
                self.notifier.send_notification(notification_title, notification_content, task_info)
                
                return {"status": "error", "message": str(e)}
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"任务执行时发生未捕获的异常: {str(e)}\n{error_details}")
            return {"status": "error", "message": f"任务执行时发生未捕获的异常: {str(e)}"}
            
        finally:
            # 任务完成，从运行列表中移除
            with self.lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
            
            # 如果创建了新的应用上下文，需要释放它
            if app_context:
                app_context.pop()
    
    def _execute_task_with_alist_sync(self, task, task_id, instance_id):
        """使用AlistSync执行任务"""
        from app.alist_sync import main as alist_sync_main
        from app.alist_sync import logger as alist_sync_logger
        
        # 获取数据管理器
        data_manager = current_app.config['DATA_MANAGER']
        
        try:
            # 获取连接信息
            connection_id = task.get("connection_id")
            if not connection_id:
                raise ValueError("任务未指定连接ID")
            
            connection = data_manager.get_connection(connection_id)
            if not connection:
                raise ValueError(f"找不到ID为{connection_id}的连接")
            
            data_manager._append_task_log(task_id, instance_id, f"使用连接 {connection.get('name', connection_id)} 执行任务")
            
            # 准备参数
            sync_type = task.get("sync_type", "file_sync")
            source_connection_id = task.get("source_connection_id")
            target_connection_ids = task.get("target_connection_ids", [])
            source_path = task.get("source_path", "/")
            target_path = task.get("target_path", "/")
            
            # 设置环境变量，确保使用正确的连接信息
            os.environ["BASE_URL"] = connection.get("server", "")
            os.environ["USERNAME"] = connection.get("username", "")
            os.environ["PASSWORD"] = connection.get("password", "")
            os.environ["TOKEN"] = connection.get("token", "")
            
            data_manager._append_task_log(task_id, instance_id, f"设置连接: 服务器={os.environ['BASE_URL']}, 用户名={os.environ['USERNAME']}")
            
            # 根据任务类型决定操作
            if sync_type == "file_move":
                os.environ["MOVE_FILE"] = "true"
                data_manager._append_task_log(task_id, instance_id, "设置为文件移动模式")
            else:
                os.environ["MOVE_FILE"] = "false"
                data_manager._append_task_log(task_id, instance_id, "设置为文件同步模式")
            
            # 设置删除差异项行为
            os.environ["SYNC_DELETE_ACTION"] = task.get("sync_diff_action", "none")
            data_manager._append_task_log(task_id, instance_id, f"设置差异项处理方式: {os.environ['SYNC_DELETE_ACTION']}")
            
            # 设置同步目录
            dir_pairs = []
            exclude_dirs = []
            for target_id in target_connection_ids:
                # 修复source_connection_id和target_connection_ids为路径格式的情况
                source_pair = source_connection_id
                if isinstance(source_connection_id, str) and not source_connection_id.isdigit():
                    # 如果source_connection_id是路径格式，则直接使用
                    source_pair = f"{source_connection_id}"
                else:
                    # 否则添加"/"前缀
                    source_pair = f"/{source_connection_id}"
                
                target_pair = target_id
                if isinstance(target_id, str) and not target_id.isdigit():
                    # 如果target_id是路径格式，则直接使用
                    target_pair = f"{target_id}"
                else:
                    # 否则添加"/"前缀
                    target_pair = f"/{target_id}"
                
                # 构建完整的目录对
                dir_pair = f"/{source_pair}/{source_path}:/{target_pair}/{target_path}".replace('//', '/')
                dir_pairs.append(dir_pair)

                if task.get("exclude_dirs"):
                    excludes = task.get("exclude_dirs").split(",")
                    for exclude in excludes:
                        exclude_dir = f"{source_pair}/{exclude}".replace('//', '/')
                        exclude_dirs.append(exclude_dir)
            
            if dir_pairs:
                os.environ["DIR_PAIRS"] = ";".join(dir_pairs)
                data_manager._append_task_log(task_id, instance_id, f"设置同步目录对: {os.environ['DIR_PAIRS']}")
                
                # 设置排除目录
                if exclude_dirs:
                    os.environ["EXCLUDE_DIRS"] = ",".join(exclude_dirs)
                    data_manager._append_task_log(task_id, instance_id, f"设置排除目录: {os.environ['EXCLUDE_DIRS']}")
                
                # 设置排除文件
                if task.get("file_filter"):
                    os.environ["REGEX_PATTERNS"] = task.get("file_filter")
                    data_manager._append_task_log(task_id, instance_id, f"设置文件过滤: {os.environ['REGEX_PATTERNS']}")
                
                # 设置最小/最大文件大小
                if task.get("size_min"):
                    os.environ["SIZE_MIN"] = str(task.get("size_min"))
                    data_manager._append_task_log(task_id, instance_id, f"设置最小文件大小: {os.environ['SIZE_MIN']}")

                if task.get("size_max"):
                    os.environ["SIZE_MAX"] = str(task.get("size_max"))
                    data_manager._append_task_log(task_id, instance_id, f"设置最大文件大小: {os.environ['SIZE_MAX']}")
                
                # 执行主函数
                data_manager._append_task_log(task_id, instance_id, "开始执行同步...")
                
                # 创建一个自定义日志处理器，将日志输出到任务日志文件
                class TaskLogHandler(logging.Handler):
                    def emit(self, record):
                        log_message = self.format(record)
                        data_manager._append_task_log(task_id, instance_id, log_message)
                
                # 获取alist_sync的logger并添加自定义处理器
                if alist_sync_logger:
                    task_log_handler = TaskLogHandler()
                    formatter = logging.Formatter('%(message)s')
                    task_log_handler.setFormatter(formatter)
                    alist_sync_logger.addHandler(task_log_handler)
                
                # 执行主函数
                alist_sync_main()
                
                # 如果有添加自定义处理器，需要移除
                if alist_sync_logger and 'task_log_handler' in locals():
                    alist_sync_logger.removeHandler(task_log_handler)
                
                return {"status": "success", "message": "同步任务执行成功", "dir_pairs": dir_pairs}
            else:
                return {"status": "error", "message": "未配置有效的目录对"}
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            data_manager._append_task_log(task_id, instance_id, f"执行出错: {str(e)}\n{error_details}")
            raise
    
    def _one_way_sync(self, source_conn, target_conn, source_path, target_path, task):
        """执行单向同步"""
        # 模拟同步过程
        data_manager = current_app.config['DATA_MANAGER']
        settings = data_manager.get_settings()
        
        # 列出源目录文件
        source_files = self._list_files(source_conn, source_path)
        if source_files.get("status") != "success":
            return source_files
        
        # 列出目标目录文件
        target_files = self._list_files(target_conn, target_path)
        if target_files.get("status") != "success":
            return target_files
        
        # 比较文件列表，找出需要同步的文件
        to_sync = []
        source_file_dict = {f["name"]: f for f in source_files.get("data", [])}
        target_file_dict = {f["name"]: f for f in target_files.get("data", [])}
        
        for name, source_file in source_file_dict.items():
            if source_file["type"] == "folder":
                # 如果是文件夹且目标不存在，创建文件夹
                if name not in target_file_dict:
                    to_sync.append({
                        "action": "create_folder",
                        "path": os.path.join(target_path, name)
                    })
            else:
                # 如果是文件，检查是否需要同步
                if name not in target_file_dict or target_file_dict[name]["size"] != source_file["size"]:
                    to_sync.append({
                        "action": "sync_file",
                        "source_path": os.path.join(source_path, name),
                        "target_path": os.path.join(target_path, name),
                        "size": source_file["size"]
                    })
        
        # 执行同步
        success_count = 0
        error_count = 0
        
        for item in to_sync:
            if item["action"] == "create_folder":
                result = self._create_folder(target_conn, item["path"])
            else:
                result = self._sync_file(
                    source_conn, 
                    target_conn, 
                    item["source_path"], 
                    item["target_path"],
                    item["size"]
                )
            
            if result.get("status") == "success":
                success_count += 1
            else:
                error_count += 1
                # 记录错误日志
                data_manager.add_log({
                    "task_id": task["id"],
                    "level": "ERROR",
                    "message": f"同步项目失败: {item['source_path'] if 'source_path' in item else item['path']}",
                    "details": result.get("message")
                })
        
        # 返回结果摘要
        total = len(to_sync)
        message = f"同步完成，共 {total} 项，成功 {success_count} 项，失败 {error_count} 项"
        
        return {
            "status": "success" if error_count == 0 else "partial",
            "message": message,
            "details": {
                "total": total,
                "success": success_count,
                "error": error_count
            }
        }
    
    def _list_files(self, connection, path):
        """列出指定路径的文件和文件夹"""
        # 模拟 API 调用
        # 实际项目中应通过 Alist API 获取文件列表
        
        # 简单模拟返回一些文件
        if path == "/":
            return {
                "status": "success",
                "data": [
                    {"name": "文档", "type": "folder", "size": 0},
                    {"name": "图片", "type": "folder", "size": 0},
                    {"name": "视频", "type": "folder", "size": 0},
                    {"name": "测试文件.txt", "type": "file", "size": 1024}
                ]
            }
        elif path == "/文档":
            return {
                "status": "success",
                "data": [
                    {"name": "报告.docx", "type": "file", "size": 15360},
                    {"name": "数据.xlsx", "type": "file", "size": 8192}
                ]
            }
        else:
            return {
                "status": "success",
                "data": []
            }
    
    def _create_folder(self, connection, path):
        """在目标连接上创建文件夹"""
        # 模拟创建文件夹
        return {"status": "success", "message": f"文件夹创建成功: {path}"}
    
    def _sync_file(self, source_conn, target_conn, source_path, target_path, size):
        """同步单个文件"""
        # 模拟文件同步过程
        # 这里应该实现实际的文件传输逻辑，包括下载和上传
        
        # 简单模拟一个耗时操作
        time.sleep(0.5)
        
        return {"status": "success", "message": f"文件同步成功: {source_path} -> {target_path}"}
    
    def stop_task(self, task_id):
        """停止正在运行的任务"""
        with self.lock:
            if task_id in self.running_tasks:
                # 实际项目中，应该有机制中断正在运行的任务
                del self.running_tasks[task_id]
                
                # 更新任务状态
                data_manager = current_app.config['DATA_MANAGER']
                data_manager.update_task_status(task_id, "stopped")
                
                return {"status": "success", "message": "任务已停止"}
            else:
                return {"status": "error", "message": "任务未在运行"}
    
    def reload_scheduler(self):
        """重新加载调度器中的所有任务"""
        try:
            current_app.logger.info("开始重新加载调度器...")
            
            # 获取数据管理器
            data_manager = current_app.config['DATA_MANAGER']
            
            # 获取所有任务
            tasks = data_manager.get_tasks()
            
            # 清除现有的所有任务，但保留日志清理等系统任务
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                if job.id.startswith('task_'):
                    self.scheduler.remove_job(job.id)
                    current_app.logger.debug(f"已移除任务: {job.id}")
            
            # 重新加载所有启用的任务
            loaded_count = 0
            for task in tasks:
                if task.get("enabled", True):
                    self.schedule_task(task)
                    loaded_count += 1
            
            current_app.logger.info(f"已重新加载 {loaded_count} 个任务到调度器")
            
            # 更新所有任务的下次运行时间
            self._update_all_next_run_times()
            
            # 列出当前所有计划任务
            job_info = []
            for job in self.scheduler.get_jobs():
                job_info.append({
                    "id": job.id,
                    "next_run": str(job.next_run_time) if job.next_run_time else None
                })
                current_app.logger.info(f"计划任务: {job.id}, 下次运行: {job.next_run_time or '未计划'}")
            
            return {
                "status": "success",
                "message": "调度器已重新加载",
                "loaded_tasks": loaded_count,
                "jobs": job_info
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            current_app.logger.error(f"重新加载调度器失败: {str(e)}")
            current_app.logger.error(error_details)
            raise
    
    def reload_tasks(self):
        """reload_tasks方法（兼容性别名），重新加载任务列表"""
        # 这个方法是reload_scheduler的别名，提供向后兼容性
        current_app.logger.info("调用reload_tasks()方法（别名），将重定向到reload_scheduler()")
        return self.reload_scheduler()
    
    def shutdown(self):
        """关闭调度器"""
        self.scheduler.shutdown() 