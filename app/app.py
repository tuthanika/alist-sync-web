from flask import Flask, current_app
from apscheduler.schedulers.background import BackgroundScheduler
import os
import logging
import time
from datetime import datetime, timedelta
from app.utils.data_manager import DataManager
from app.utils.sync_manager import SyncManager
import pytz
import traceback

def init_app(app):
    """初始化应用"""
    # 配置日志
    logger = logging.getLogger()
    app.logger = logger
    logger.info("初始化应用...")
    
    # 初始化数据管理器(如果尚未初始化)
    if 'DATA_MANAGER' not in app.config:
        data_manager = DataManager()
        app.config['DATA_MANAGER'] = data_manager
    else:
        data_manager = app.config['DATA_MANAGER']
    
    # 初始化并保存同步管理器
    app.logger.info("初始化同步管理器...")
    
    # 必须在应用上下文中创建SyncManager实例
    with app.app_context():
        sync_manager = SyncManager()
        app.config['SYNC_MANAGER'] = sync_manager
        
        # 初始化同步管理器的调度器
        app.logger.info("正在加载任务到调度器...")
        try:
            sync_manager.initialize_scheduler()
            app.logger.info("任务调度器初始化完成")
        except Exception as e:
            app.logger.error(f"初始化任务调度器失败: {str(e)}")
            app.logger.error(traceback.format_exc())
    
        # 将日志清理任务也加入到同步管理器的调度器中，避免使用两个调度器
        try:
            # 创建日志清理的调度任务
            @sync_manager.scheduler.scheduled_job('cron', hour=3, minute=0, id='log_cleanup_job')
            def clean_old_logs():
                """定期清理过期日志"""
                # 确保在应用上下文中运行
                with app.app_context():
                    app.logger.info("开始清理过期日志...")
                    
                    try:
                        # 获取日志保留天数
                        settings = data_manager.get_settings()
                        keep_log_days = settings.get("keep_log_days", 7)
                        
                        # 清理系统日志
                        data_manager.clear_old_logs(keep_log_days)
                        app.logger.info(f"系统日志清理完成，保留{keep_log_days}天内的日志")
                        
                        # 清理任务实例和任务日志
                        data_manager.clear_old_task_instances(keep_log_days)
                        app.logger.info(f"任务实例和任务日志清理完成，保留{keep_log_days}天内的记录")
                        
                        # 清理主日志文件 alist_sync.log
                        data_manager.clear_main_log_files(keep_log_days)
                        app.logger.info(f"主日志文件清理完成，保留{keep_log_days}天内的日志")
                        
                    except Exception as e:
                        app.logger.error(f"清理日志时出错: {str(e)}")
                        app.logger.error(traceback.format_exc())
            
            app.logger.info("日志清理任务已添加到调度器")
            
            # 输出所有已计划任务的状态
            jobs = sync_manager.scheduler.get_jobs()
            for job in jobs:
                app.logger.info(f"计划任务: {job.id}, 下次运行: {job.next_run_time}")
                
        except Exception as e:
            app.logger.error(f"添加日志清理任务失败: {str(e)}")
            app.logger.error(traceback.format_exc())
    
    return app 