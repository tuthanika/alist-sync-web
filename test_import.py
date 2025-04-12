"""
测试导入模块
"""
import os
import sys

# 设置Python路径，确保可以导入app模块
sys.path.insert(0, os.path.abspath('.'))

try:
    print("尝试导入app模块...")
    import app
    print("app模块导入成功")

    print("\n尝试导入app.alist_sync模块...")
    from app.alist_sync import AlistSync, main, logger
    print("app.alist_sync模块导入成功")
    print(f"- AlistSync: {AlistSync}")
    print(f"- main: {main}")
    print(f"- logger: {logger}")

    print("\n尝试导入app.routes模块...")
    from app.routes import main_bp, api_bp, auth_bp
    print("app.routes模块导入成功")
    print(f"- main_bp: {main_bp}")
    print(f"- api_bp: {api_bp}")
    print(f"- auth_bp: {auth_bp}")

    print("\n尝试导入app.utils.sync_manager模块...")
    from app.utils.sync_manager import SyncManager
    print("app.utils.sync_manager模块导入成功")
    print(f"- SyncManager: {SyncManager}")

    print("\n所有测试都通过了，导入正常！")
except Exception as e:
    print(f"\n导入出错: {e}")
    import traceback
    traceback.print_exc() 