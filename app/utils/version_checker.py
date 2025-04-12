import os
import re
import json
import requests
import logging
from datetime import datetime, timedelta

# 版本缓存文件
VERSION_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                               'data/config/version_cache.json')

# Github API URL
GITHUB_API_URL = "https://api.github.com/repos/xjxjin/alist-sync/releases/latest"

def get_current_version():
    """获取当前系统版本"""
    try:
        version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'VERSION')
        
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                version = f.read().strip()
                return version
    except Exception as e:
        logging.error(f"获取当前版本失败: {str(e)}")
    
    return "未知"

def get_latest_version():
    """从GitHub获取最新版本"""
    # 检查是否存在缓存
    if os.path.exists(VERSION_CACHE_FILE):
        try:
            with open(VERSION_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                
                # 检查缓存是否过期（24小时）
                cache_time = datetime.fromisoformat(cache_data.get('timestamp'))
                if datetime.now() - cache_time < timedelta(hours=24):
                    return cache_data.get('version'), cache_data.get('download_url', "")
        except Exception as e:
            logging.error(f"读取版本缓存失败: {str(e)}")
    
    # 缓存不存在或已过期，从GitHub获取
    try:
        response = requests.get(GITHUB_API_URL, timeout=5)
        if response.status_code == 200:
            release_data = response.json()
            latest_version = release_data.get('tag_name', '').lstrip('v')
            download_url = release_data.get('html_url', '')
            
            # 更新缓存
            cache_data = {
                'version': latest_version,
                'download_url': download_url,
                'timestamp': datetime.now().isoformat()
            }
            
            os.makedirs(os.path.dirname(VERSION_CACHE_FILE), exist_ok=True)
            with open(VERSION_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            
            return latest_version, download_url
    except Exception as e:
        logging.error(f"获取GitHub最新版本失败: {str(e)}")
    
    # 如果获取失败但有缓存，返回缓存中的版本
    if os.path.exists(VERSION_CACHE_FILE):
        try:
            with open(VERSION_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                return cache_data.get('version'), cache_data.get('download_url', "")
        except:
            pass
    
    return None, ""

def has_new_version():
    """检查是否有新版本"""
    current = get_current_version()
    latest, _ = get_latest_version()
    
    if not latest:
        return False, current, None
    
    # 版本比较
    current_parts = current.split('.')
    latest_parts = latest.split('.')
    
    for i in range(max(len(current_parts), len(latest_parts))):
        c_val = int(current_parts[i]) if i < len(current_parts) else 0
        l_val = int(latest_parts[i]) if i < len(latest_parts) else 0
        
        if l_val > c_val:
            return True, current, latest
        elif c_val > l_val:
            return False, current, latest
    
    return False, current, latest 