from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from app.utils.sync_manager import SyncManager
import importlib.util
import os
import sys
import logging
from datetime import datetime
import json
import time
from werkzeug.utils import secure_filename
from app.utils.data_manager import DataManager
from app.alist_sync import AlistSync
import pytz
from functools import wraps

main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)
auth_bp = Blueprint('auth', __name__)

# 认证相关路由
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('请输入用户名和密码', 'danger')
            return render_template('login.html')
        
        data_manager = current_app.config['DATA_MANAGER']
        user = data_manager.authenticate_user(username, password)
        
        if user:
            # 设置会话数据
            session['logged_in'] = True
            session['username'] = user['username']
            session['user_id'] = user['id']
            
            # 记录登录日志
            data_manager.add_log({
                "level": "INFO",
                "message": f"用户登录成功: {username}",
                "details": {"ip": request.remote_addr}
            })
            
            return redirect(url_for('main.index'))
        else:
            flash('用户名或密码错误', 'danger')
            return render_template('login.html')
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """注销"""
    if 'username' in session:
        username = session['username']
        # 记录登出日志
        data_manager = current_app.config['DATA_MANAGER']
        data_manager.add_log({
            "level": "INFO",
            "message": f"用户登出: {username}",
            "details": None
        })
    
    # 清除会话
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """用户资料页面"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'POST':
        action = request.form.get('action')
        username = session.get('username')
        
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # 验证当前密码
            if not data_manager.authenticate_user(username, current_password):
                flash('当前密码不正确', 'danger')
                return redirect(url_for('auth.profile'))
            
            # 验证新密码
            if new_password != confirm_password:
                flash('两次输入的新密码不一致', 'danger')
                return redirect(url_for('auth.profile'))
            
            # 更新密码
            data_manager.update_user_password(username, new_password)
            flash('密码已成功更新', 'success')
            
        elif action == 'change_username':
            new_username = request.form.get('new_username')
            password = request.form.get('password')
            
            # 验证密码
            if not data_manager.authenticate_user(username, password):
                flash('密码不正确', 'danger')
                return redirect(url_for('auth.profile'))
            
            # 更新用户名
            if data_manager.update_username(username, new_username):
                session['username'] = new_username
                flash('用户名已成功更新', 'success')
            else:
                flash('用户名更新失败，可能该用户名已存在', 'danger')
    
    return render_template('profile.html')

@main_bp.route('/')
def index():
    """首页 - 概述与监控面板"""
    return render_template('index.html')

@main_bp.route('/connections')
def connections():
    """连接管理页面"""
    data_manager = current_app.config['DATA_MANAGER']
    connections = data_manager.get_connections()
    return render_template('connections.html', connections=connections)

@main_bp.route('/tasks')
def tasks():
    """任务管理页面"""
    data_manager = current_app.config['DATA_MANAGER']
    tasks = data_manager.get_tasks()
    return render_template('tasks.html', tasks=tasks)

@main_bp.route('/task-instances')
def task_instances():
    """任务实例页面"""
    data_manager = current_app.config['DATA_MANAGER']
    instances = data_manager.get_task_instances(None, 100)  # 显示最近100条实例记录
    return render_template('task_instances.html', instances=instances)

@main_bp.route('/settings')
def settings():
    """设置页面"""
    data_manager = current_app.config['DATA_MANAGER']
    settings = data_manager.get_settings()
    return render_template('settings.html', settings=settings)

@main_bp.route('/logs')
def logs():
    """日志查看页面"""
    data_manager = current_app.config['DATA_MANAGER']
    logs = data_manager.get_logs()
    return render_template('logs.html', logs=logs)

# API 路由
@api_bp.route('/connections', methods=['GET', 'POST'])
def api_connections():
    """连接 API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'POST':
        connection_data = request.json
        data_manager.add_connection(connection_data)
        return jsonify({"status": "success", "message": "连接已添加"})
    
    return jsonify(data_manager.get_connections())

@api_bp.route('/connections/<int:conn_id>', methods=['GET', 'PUT', 'DELETE'])
def api_connection(conn_id):
    """单个连接 API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'PUT':
        connection_data = request.json
        # 调试日志：输出更新连接数据
        current_app.logger.debug(f"更新连接数据: {json.dumps(connection_data)}")
        
        # 确保状态字段存在
        if 'status' not in connection_data:
            connection_data['status'] = 'offline'
            current_app.logger.debug("未指定连接状态，设置为offline")
        
        data_manager.update_connection(conn_id, connection_data)
        return jsonify({"status": "success", "message": "连接已更新"})
    
    elif request.method == 'DELETE':
        data_manager.delete_connection(conn_id)
        return jsonify({"status": "success", "message": "连接已删除"})
    
    # GET 方法 - 获取连接信息
    connection = data_manager.get_connection(conn_id)
    if connection:
        # 创建返回的数据对象，包含所有信息（包括密码）
        return jsonify(connection)
    
    return jsonify({"status": "error", "message": "连接不存在"}), 404

@api_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """测试连接接口"""
    try:
        data = request.get_json()
        conn_id = data.get('connection_id') # 获取连接ID，如果有的话
        
        # 记录连接测试日志
        data_manager = current_app.config['DATA_MANAGER']
        
        # 记录请求数据到日志（调试用）
        current_app.logger.debug(f"测试连接请求数据: {json.dumps(data)}")
        
        data_manager.add_log({
            "level": "INFO",
            "message": f"测试连接: {data.get('server', '')}",
            "details": {"username": data.get('username')}
        })
        
        # 创建AlistSync实例进行连接测试
        alist = AlistSync(
            data.get('server'),
            data.get('username'),
            data.get('password'),
            data.get('token')
        )
        
        # 尝试登录验证连接
        login_success = alist.login()
        
        if login_success:
            # 获取测试成功后的token
            token = alist.token
            
            # 更新连接状态为在线，并保存token
            if conn_id:
                conn = data_manager.get_connection(int(conn_id))
                if conn:
                    conn['status'] = 'online'
                    conn['token'] = token  # 更新token
                    data_manager.update_connection(int(conn_id), conn)
                    current_app.logger.debug(f"更新连接状态为在线: {conn_id}")
            
            # 连接成功
            data_manager.add_log({
                "level": "INFO",
                "message": f"连接测试成功: {data.get('server', '')}",
                "details": {"username": data.get('username')}
            })
            
            response_data = {
                "status": "success",
                "message": "连接测试成功",
                "data": {
                    "token": token,
                    "connection_status": "online"
                }
            }
            current_app.logger.debug(f"测试连接响应数据: {json.dumps(response_data)}")
            return jsonify(response_data)
        else:
            # 更新连接状态为离线
            if conn_id:
                conn = data_manager.get_connection(int(conn_id))
                if conn:
                    conn['status'] = 'offline'
                    data_manager.update_connection(int(conn_id), conn)
                    current_app.logger.debug(f"更新连接状态为离线: {conn_id}")
            
            # 连接失败
            data_manager.add_log({
                "level": "ERROR",
                "message": f"连接测试失败: {data.get('server', '')}",
                "details": {"username": data.get('username'), "error": "登录验证失败"}
            })
            
            response_data = {
                "status": "error",
                "message": "连接测试失败：验证错误，请检查服务器地址、用户名、密码或令牌",
                "data": {
                    "connection_status": "offline"
                }
            }
            current_app.logger.debug(f"测试连接响应数据: {json.dumps(response_data)}")
            return jsonify(response_data)
    except Exception as e:
        # 如果有连接ID，更新其状态为离线
        if 'data' in locals() and 'conn_id' in data and data['conn_id']:
            if 'data_manager' in locals():
                conn = data_manager.get_connection(int(data['conn_id']))
                if conn:
                    conn['status'] = 'offline'
                    data_manager.update_connection(int(data['conn_id']), conn)
        
        # 发生异常
        if 'data_manager' in locals():
            data_manager.add_log({
                "level": "ERROR",
                "message": f"连接测试异常: {data.get('server', '') if 'data' in locals() else 'unknown'}",
                "details": {"error": str(e)}
            })
        
        return jsonify({
            "status": "error",
            "message": f"连接测试失败: {str(e)}",
            "data": {
                "connection_status": "offline"
            }
        }), 500
    finally:
        # 确保关闭连接
        if 'alist' in locals():
            alist.close()

@api_bp.route('/tasks', methods=['GET', 'POST'])
def api_tasks():
    """任务 API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'POST':
        task_data = request.json
        
        # 确保connection_id是整数类型
        if 'connection_id' in task_data:
            try:
                task_data['connection_id'] = int(task_data['connection_id'])
            except (ValueError, TypeError):
                # 如果无法转换为整数，尝试设置为第一个可用连接的ID
                connections = data_manager.get_connections()
                if connections:
                    task_data['connection_id'] = connections[0].get('connection_id')
                else:
                    task_data['connection_id'] = None
        
        data_manager.add_task(task_data)
        
        # 如果任务添加成功，将任务添加到调度器
        if 'SYNC_MANAGER' in current_app.config and task_data.get("schedule"):
            task_id = task_data.get("id")
            if not task_id:
                # 如果任务数据中没有ID，获取最新添加的任务
                tasks = data_manager.get_tasks()
                if tasks:
                    task_id = tasks[-1].get("id")
            
            if task_id:
                sync_manager = current_app.config['SYNC_MANAGER']
                updated_task = data_manager.get_task(task_id)
                if updated_task:
                    # 添加任务到调度器
                    sync_manager.schedule_task(updated_task)
                    current_app.logger.info(f"新任务 {task_id} 已添加到调度器")
        
        return jsonify({"status": "success", "message": "任务已添加"})
    
    return jsonify(data_manager.get_tasks())

@api_bp.route('/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
def api_task(task_id):
    """单个任务 API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'PUT':
        task_data = request.json
        
        # 确保connection_id是整数类型
        if 'connection_id' in task_data:
            try:
                task_data['connection_id'] = int(task_data['connection_id'])
            except (ValueError, TypeError):
                # 如果无法转换为整数，尝试设置为第一个可用连接的ID
                connections = data_manager.get_connections()
                if connections:
                    task_data['connection_id'] = connections[0].get('connection_id')
                else:
                    task_data['connection_id'] = None
        
        data_manager.update_task(task_id, task_data)
        return jsonify({"status": "success", "message": "任务已更新"})
    
    elif request.method == 'DELETE':
        data_manager.delete_task(task_id)
        return jsonify({"status": "success", "message": "任务已删除"})
    
    return jsonify(data_manager.get_task(task_id))

@api_bp.route('/tasks/<int:task_id>/run', methods=['POST'])
def api_run_task(task_id):
    """立即运行任务"""
    try:
        # 获取任务信息
        data_manager = current_app.config['DATA_MANAGER']
        task = data_manager.get_task(task_id)
        
        if not task:
            return jsonify({
                "status": "error", 
                "message": f"任务不存在: {task_id}"
            }), 404
        
        # 记录任务启动日志
        data_manager.add_log({
            "level": "INFO",
            "message": f"手动启动任务: {task.get('name', f'任务 {task_id}')}",
            "details": {"task_id": task_id, "from": request.remote_addr}
        })
        
        # 创建同步管理器并运行任务
        sync_manager = SyncManager()
        result = sync_manager.run_task(task_id)
        
        # 记录任务运行结果
        if result.get("status") == "success":
            data_manager.add_log({
                "level": "INFO",
                "message": f"任务启动成功: {task.get('name', f'任务 {task_id}')}",
                "details": {"task_id": task_id, "instance_id": result.get("instance_id")}
            })
        else:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"任务启动失败: {task.get('name', f'任务 {task_id}')}",
                "details": {"task_id": task_id, "error": result.get("message")}
            })
        
        return jsonify(result)
    except Exception as e:
        # 记录异常
        if 'data_manager' in locals() and 'task' in locals():
            data_manager.add_log({
                "level": "ERROR",
                "message": f"任务启动异常: {task.get('name', f'任务 {task_id}')}",
                "details": {"task_id": task_id, "error": str(e)}
            })
        
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"任务启动异常: {error_details}")
        
        return jsonify({
            "status": "error",
            "message": f"任务运行失败: {str(e)}"
        }), 500

@api_bp.route('/task-instances', methods=['GET'])
def api_task_instances():
    """获取任务实例列表"""
    data_manager = current_app.config['DATA_MANAGER']
    task_id = request.args.get('task_id')
    limit = request.args.get('limit', 50, type=int)
    
    if task_id:
        # 获取指定任务的实例
        instances = data_manager.get_task_instances(int(task_id), limit)
    else:
        # 获取所有任务的实例
        instances = data_manager.get_task_instances(None, limit)
    
    return jsonify(instances)

@api_bp.route('/task-instances/<int:instance_id>', methods=['GET'])
def api_task_instance(instance_id):
    """获取单个任务实例"""
    data_manager = current_app.config['DATA_MANAGER']
    instance = data_manager.get_task_instance(instance_id)
    
    if not instance:
        return jsonify({"status": "error", "message": "任务实例不存在"}), 404
    
    return jsonify(instance)

@api_bp.route('/task-instances/<int:instance_id>/logs', methods=['GET'])
def api_task_instance_logs(instance_id):
    """获取任务实例的日志"""
    data_manager = current_app.config['DATA_MANAGER']
    instance = data_manager.get_task_instance(instance_id)
    
    if not instance:
        return jsonify({"status": "error", "message": "任务实例不存在"}), 404
    
    task_id = instance.get('task_id')
    logs = data_manager.get_task_log(task_id, instance_id)
    
    return jsonify({
        "status": "success",
        "instance_id": instance_id,
        "task_id": task_id,
        "logs": logs
    })

@api_bp.route('/settings', methods=['GET', 'PUT'])
def api_settings():
    """设置 API"""
    data_manager = current_app.config['DATA_MANAGER']
    
    if request.method == 'PUT':
        settings_data = request.json
        data_manager.update_settings(settings_data)
        return jsonify({"status": "success", "message": "设置已更新"})
    
    return jsonify(data_manager.get_settings())

@api_bp.route('/storages', methods=['GET'])
def get_storages():
    """获取存储列表"""
    try:
        conn_id = request.args.get('conn_id')
        if not conn_id:
            return jsonify({"status": "error", "message": "缺少连接ID参数"}), 400
        
        # 记录请求日志
        data_manager = current_app.config['DATA_MANAGER']
        data_manager.add_log({
            "level": "INFO",
            "message": f"获取连接 {conn_id} 的存储列表",
            "details": {"request_from": request.remote_addr}
        })
        
        # 尝试将conn_id转换为整数
        try:
            conn_id = int(conn_id)
        except (ValueError, TypeError):
            data_manager.add_log({
                "level": "ERROR",
                "message": f"连接ID格式错误",
                "details": {"error": f"无效的连接ID: {conn_id}"}
            })
            return jsonify({"status": "error", "message": f"无效的连接ID: {conn_id}"}), 400
        
        # 获取连接信息，使用connection_id字段
        connection = data_manager.get_connection(conn_id)
        
        if not connection:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"获取存储列表失败",
                "details": {"error": f"找不到ID为{conn_id}的连接"}
            })
            return jsonify({"status": "error", "message": f"找不到ID为{conn_id}的连接"}), 404
        
        # 创建AlistSync实例
        alist = AlistSync(
            connection.get('server'),
            connection.get('username'),
            connection.get('password'),
            connection.get('token')
        )
        
        # 尝试登录
        login_success = alist.login()
        if not login_success:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"获取存储列表失败",
                "details": {"error": "登录失败", "connection_id": conn_id}
            })
            return jsonify({"status": "error", "message": "登录失败，无法获取存储列表"}), 401
        
        try:
            # 获取存储列表
            storage_list = alist.get_storage_list()
            
            # 如果获取到的不是列表，进行转换
            if not isinstance(storage_list, list):
                storage_list = []
            
            # 格式化存储列表
            formatted_storages = []
            for storage in storage_list:
                # 如果是字典格式
                if isinstance(storage, dict):
                    if 'mount_path' in storage:
                        formatted_storages.append({
                            'id': storage.get('mount_path', ''),
                            'name': storage.get('mount_path', '') + (f" ({storage.get('remark', '')})" if storage.get('remark') else '')
                        })
                    elif 'id' in storage and 'name' in storage:
                        formatted_storages.append(storage)
                    else:
                        # 使用字典的第一个值作为ID和名称
                        storage_id = next(iter(storage.values()), '')
                        formatted_storages.append({
                            'id': storage_id,
                            'name': storage_id
                        })
                # 如果是字符串格式
                elif isinstance(storage, str):
                    formatted_storages.append({
                        'id': storage,
                        'name': storage
                    })
            
            if not formatted_storages:
                data_manager.add_log({
                    "level": "WARNING",
                    "message": f"获取连接 {conn_id} 的存储列表为空",
                    "details": {"connection_id": conn_id}
                })
                return jsonify({
                    "status": "success", 
                    "data": [],
                    "message": "存储列表为空"
                })
            
            # 记录成功日志
            data_manager.add_log({
                "level": "INFO",
                "message": f"获取连接 {conn_id} 的存储列表成功",
                "details": {"count": len(formatted_storages)}
            })
            
            return jsonify({
                "status": "success", 
                "data": formatted_storages
            })
        except Exception as e:
            data_manager.add_log({
                "level": "ERROR",
                "message": f"处理存储列表数据失败",
                "details": {"error": str(e), "connection_id": conn_id}
            })
            import traceback
            error_details = traceback.format_exc()
            current_app.logger.error(f"处理存储列表异常: {error_details}")
            return jsonify({"status": "error", "message": f"处理存储列表数据失败: {str(e)}"}), 500
            
    except Exception as e:
        # 记录错误
        if 'data_manager' in locals():
            data_manager.add_log({
                "level": "ERROR",
                "message": f"获取存储列表失败",
                "details": {"error": str(e), "connection_id": conn_id if 'conn_id' in locals() else None}
            })
        
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"获取存储列表异常: {error_details}")
        
        return jsonify({"status": "error", "message": f"获取存储列表失败: {str(e)}"}), 500
    finally:
        # 确保关闭连接
        if 'alist' in locals():
            alist.close()

@api_bp.route('/dashboard/stats', methods=['GET'])
def dashboard_stats():
    """获取仪表板统计数据"""
    try:
        data_manager = current_app.config['DATA_MANAGER']
        
        # 获取连接数量
        connections = data_manager.get_connections()
        connection_count = len(connections)
        
        # 获取任务数量和状态
        tasks = data_manager.get_tasks()
        task_count = len(tasks)
        
        # 统计不同状态的任务数量
        completed_task_count = sum(1 for task in tasks if task.get('status') == 'completed')
        running_task_count = sum(1 for task in tasks if task.get('status') == 'running')
        failed_task_count = sum(1 for task in tasks if task.get('status') == 'failed')
        pending_task_count = task_count - completed_task_count - running_task_count - failed_task_count
        
        # 获取活跃任务数量
        active_task_count = running_task_count
        
        # 获取同步文件数量（从任务实例中统计）
        synced_files_count = 0
        task_instances = data_manager.get_task_instances(None, 100)
        for instance in task_instances:
            if instance.get('status') == 'completed':
                result = instance.get('result', {})
                if result.get('details') and 'total' in result.get('details', {}):
                    synced_files_count += result.get('details', {}).get('total', 0)
        
        # 统计连接类型分布
        connection_types = []
        connection_type_counts = []
        connection_type_map = {}
        
        for conn in connections:
            server_url = conn.get('server', '')
            if '/dav/aliyundrive' in server_url or 'alipan' in server_url:
                conn_type = '阿里云盘'
            elif '/dav/baidu' in server_url or 'pan.baidu' in server_url:
                conn_type = '百度网盘'
            elif '/dav/quark' in server_url or 'quark' in server_url:
                conn_type = '夸克网盘'
            elif '/dav/189cloud' in server_url or '189' in server_url:
                conn_type = '天翼云盘'
            elif '/dav/onedrive' in server_url or 'onedrive' in server_url:
                conn_type = 'OneDrive'
            else:
                conn_type = '其他'
            
            if conn_type in connection_type_map:
                connection_type_map[conn_type] += 1
            else:
                connection_type_map[conn_type] = 1
        
        for conn_type, count in connection_type_map.items():
            connection_types.append(conn_type)
            connection_type_counts.append(count)
        
        # 统计任务执行时长
        task_duration_labels = ['小于1分钟', '1-5分钟', '5-15分钟', '15-30分钟', '30分钟以上']
        task_duration_counts = [0, 0, 0, 0, 0]
        
        for instance in task_instances:
            if instance.get('status') == 'completed' and instance.get('start_time') and instance.get('end_time'):
                duration_seconds = instance.get('end_time') - instance.get('start_time')
                if duration_seconds < 60:
                    task_duration_counts[0] += 1
                elif duration_seconds < 300:
                    task_duration_counts[1] += 1
                elif duration_seconds < 900:
                    task_duration_counts[2] += 1
                elif duration_seconds < 1800:
                    task_duration_counts[3] += 1
                else:
                    task_duration_counts[4] += 1
        
        # 统计每个任务的成功率
        success_rate_labels = []
        success_rate_values = []
        
        task_success_map = {}
        task_total_map = {}
        
        for instance in task_instances:
            task_id = instance.get('task_id')
            task_name = instance.get('task_name')
            
            if task_id not in task_total_map:
                task_total_map[task_id] = 0
                task_success_map[task_id] = 0
            
            task_total_map[task_id] += 1
            if instance.get('status') == 'completed':
                task_success_map[task_id] += 1
        
        # 获取任务列表并按成功率排序
        task_success_rate = []
        for task in tasks[:5]:  # 只取前5个任务
            task_id = task.get('id')
            if task_id in task_total_map and task_total_map[task_id] > 0:
                success_rate = round((task_success_map.get(task_id, 0) / task_total_map[task_id]) * 100)
                task_success_rate.append({
                    'name': task.get('name'),
                    'rate': success_rate
                })
        
        # 按成功率排序并准备数据
        task_success_rate.sort(key=lambda x: x['rate'], reverse=True)
        for item in task_success_rate:
            success_rate_labels.append(item['name'])
            success_rate_values.append(item['rate'])
        
        # 获取最近任务
        recent_tasks = sorted(tasks, key=lambda x: x.get('last_run', ''), reverse=True)[:5]
        
        return jsonify({
            "status": "success",
            "data": {
                "connection_count": connection_count,
                "task_count": task_count,
                "active_task_count": active_task_count,
                "synced_files_count": synced_files_count,
                "completed_task_count": completed_task_count,
                "running_task_count": running_task_count,
                "failed_task_count": failed_task_count,
                "pending_task_count": pending_task_count,
                "connection_types": connection_types,
                "connection_type_counts": connection_type_counts,
                "task_duration_labels": task_duration_labels,
                "task_duration_counts": task_duration_counts,
                "success_rate_labels": success_rate_labels,
                "success_rate_values": success_rate_values,
                "recent_tasks": recent_tasks
            }
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"获取仪表板数据异常: {error_details}")
        
        return jsonify({
            "status": "error",
            "message": f"获取仪表板数据失败: {str(e)}"
        }), 500

@api_bp.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    """获取调度器状态"""
    try:
        # 检查调度器是否存在于应用配置中
        sync_manager = current_app.config.get('SYNC_MANAGER')
        if not sync_manager:
            return jsonify({
                "status": "error",
                "message": "调度器未初始化",
                "running": False,
                "jobs": []
            })
        
        # 获取调度器中的任务
        scheduler = sync_manager.scheduler
        jobs = scheduler.get_jobs()
        
        job_info = []
        for job in jobs:
            job_info.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return jsonify({
            "status": "success",
            "message": "调度器正在运行",
            "running": scheduler.running,
            "job_count": len(jobs),
            "jobs": job_info
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"获取调度器状态异常: {error_details}")
        
        return jsonify({
            "status": "error",
            "message": f"获取调度器状态失败: {str(e)}",
            "running": False,
            "jobs": []
        }), 500

@api_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def api_update_task(task_id):
    """更新任务"""
    data_manager = current_app.config['DATA_MANAGER']
    task_data = request.json
    
    # 更新任务
    if data_manager.update_task(task_id, task_data):
        # 如果任务更新成功，重新加载该任务到调度器
        if 'SYNC_MANAGER' in current_app.config:
            sync_manager = current_app.config['SYNC_MANAGER']
            
            # 获取更新后的任务
            updated_task = data_manager.get_task(task_id)
            if updated_task:
                # 重新调度该任务
                sync_manager.schedule_task(updated_task)
                current_app.logger.info(f"任务 {task_id} 已重新调度")
                
                # 记录日志
                data_manager.add_log({
                    "level": "INFO",
                    "message": f"任务已更新并重新调度: {updated_task.get('name')}",
                    "details": {"task_id": task_id}
                })
        
        return jsonify({"status": "success", "message": "任务已更新"})
    
    return jsonify({"status": "error", "message": "任务更新失败"}), 404

@api_bp.route('/scheduler/reload', methods=['POST'])
def api_reload_scheduler():
    """重新加载所有任务到调度器"""
    try:
        # 获取同步管理器
        if 'SYNC_MANAGER' not in current_app.config:
            return jsonify({
                "status": "error", 
                "message": "调度器未初始化"
            }), 500
            
        sync_manager = current_app.config['SYNC_MANAGER']
        
        # 重新初始化调度器
        sync_manager.is_initialized = False  # 强制重新初始化
        sync_manager.initialize_scheduler()
        
        # 记录日志
        data_manager = current_app.config['DATA_MANAGER']
        data_manager.add_log({
            "level": "INFO",
            "message": "调度器已重新加载所有任务",
            "details": {"from": request.remote_addr}
        })
        
        # 获取所有任务信息
        jobs = sync_manager.scheduler.get_jobs()
        job_info = []
        for job in jobs:
            job_info.append({
                "id": job.id,
                "next_run": str(job.next_run_time) if job.next_run_time else None
            })
        
        return jsonify({
            "status": "success",
            "message": "调度器已重新加载",
            "jobs_count": len(jobs),
            "jobs": job_info
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"重新加载调度器失败: {str(e)}")
        current_app.logger.error(error_details)
        
        return jsonify({
            "status": "error",
            "message": f"重新加载调度器失败: {str(e)}"
        }), 500

@api_bp.route('/logs', methods=['GET'])
def api_logs():
    """获取日志列表，支持筛选"""
    data_manager = current_app.config['DATA_MANAGER']
    
    # 获取筛选参数
    level = request.args.get('level')
    task_id = request.args.get('task_id')
    search = request.args.get('search')
    timestamp = request.args.get('timestamp')
    limit = request.args.get('limit', 100, type=int)
    
    # 获取所有日志
    logs = data_manager.get_logs(limit=limit)
    
    # 应用筛选条件
    if level:
        logs = [log for log in logs if log.get('level') == level]
    
    if task_id:
        try:
            task_id = int(task_id)
            logs = [log for log in logs if log.get('task_id') == task_id]
        except (ValueError, TypeError):
            pass
    
    if timestamp:
        try:
            timestamp = int(timestamp)
            logs = [log for log in logs if log.get('timestamp') == timestamp]
        except (ValueError, TypeError):
            pass
    
    if search:
        search = search.lower()
        filtered_logs = []
        for log in logs:
            # 在消息中搜索
            if search in log.get('message', '').lower():
                filtered_logs.append(log)
                continue
                
            # 在详情中搜索
            details = log.get('details', {})
            if isinstance(details, dict):
                details_str = json.dumps(details, ensure_ascii=False).lower()
                if search in details_str:
                    filtered_logs.append(log)
                    continue
            elif isinstance(details, str) and search in details.lower():
                filtered_logs.append(log)
                
        logs = filtered_logs
    
    # 确保所有日志有 ID 字段
    for i, log in enumerate(logs):
        if 'id' not in log:
            log['id'] = i + 1
    
    return jsonify({
        "status": "success",
        "logs": logs
    })

@api_bp.route('/logs/<int:log_id>', methods=['GET'])
def api_log_detail(log_id):
    """获取单个日志详情"""
    data_manager = current_app.config['DATA_MANAGER']
    
    # 获取所有日志
    logs = data_manager.get_logs(limit=1000)
    
    # 查找指定 ID 的日志
    log = None
    for i, item in enumerate(logs):
        # 如果日志没有 ID，使用索引作为 ID
        if 'id' not in item:
            item['id'] = i + 1
            
        if item.get('id') == log_id:
            log = item
            break
    
    if not log:
        return jsonify({"status": "error", "message": "日志不存在"}), 404
    
    return jsonify({
        "status": "success",
        "log": log
    })

@api_bp.route('/logs/clear', methods=['POST'])
def api_clear_logs():
    """清空日志"""
    data_manager = current_app.config['DATA_MANAGER']
    
    try:
        # 记录清空日志操作
        data_manager.add_log({
            "level": "INFO",
            "message": "手动清空所有日志",
            "details": {"ip": request.remote_addr}
        })
        
        # 清空日志
        data_manager._write_json(data_manager.logs_file, [])
        
        return jsonify({
            "status": "success",
            "message": "日志已清空"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"清空日志失败: {str(e)}"
        }), 500

# 导入导出功能
@api_bp.route('/export', methods=['GET'])
def api_export_data():
    """导出所有数据为一个JSON文件"""
    data_manager = current_app.config['DATA_MANAGER']
    try:
        export_data = data_manager.export_data()
        response = {
            "status": "success",
            "message": "数据导出成功",
            "data": export_data
        }
        return jsonify(response)
    except Exception as e:
        current_app.logger.error(f"导出数据时发生错误: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"导出数据失败: {str(e)}"
        }), 500

@api_bp.route('/import', methods=['POST'])
def api_import_data():
    """导入数据并覆盖现有数据"""
    data_manager = current_app.config['DATA_MANAGER']
    
    try:
        import_data = request.json
        if not import_data:
            return jsonify({
                "status": "error",
                "message": "请提供有效的导入数据"
            }), 400
        
        # 不再验证标准格式的必需键，因为我们支持多种格式
        # 执行导入，默认进行备份
        result = data_manager.import_data(import_data)
        
        if result["success"]:
            # 记录日志
            format_type = result.get("details", {}).get("format", "unknown")
            data_manager.add_log({
                "level": "INFO",
                "message": f"成功导入系统数据(格式: {format_type})",
                "details": {"backup_dir": result.get("details", {}).get("backup_dir", "")}
            })
            
            # 重新加载调度器
            sync_manager = current_app.config.get('SYNC_MANAGER')
            if sync_manager:
                try:
                    sync_manager.reload_scheduler()
                    result["details"]["scheduler"] = "调度器已重新加载"
                except Exception as e:
                    result["details"]["scheduler_error"] = str(e)
            
            return jsonify({
                "status": "success",
                "message": result["message"],
                "details": result["details"]
            })
        else:
            # 记录错误日志
            data_manager.add_log({
                "level": "ERROR",
                "message": f"导入系统数据失败: {result['message']}",
                "details": result.get("details", {})
            })
            
            return jsonify({
                "status": "error",
                "message": result["message"],
                "details": result["details"]
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"导入数据时发生错误: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"导入数据失败: {str(e)}"
        }), 500

# 添加Web界面导入导出路由
@main_bp.route('/import-export')
def import_export_page():
    """导入导出页面"""
    return render_template('import_export.html')

# 注册蓝图
# ... existing code ... 