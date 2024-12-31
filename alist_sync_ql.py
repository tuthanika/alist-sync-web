import http.client
import json
import re
from datetime import datetime, timedelta
import os
import logging
from typing import List, Dict, Optional, Tuple, Union

# 配置日志记录器
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s',
                   datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

class AlistSync:
    def __init__(self, base_url: str, username: str, password: str, sync_delete_action: str = "none"):
        """
        初始化AlistSync类
        
        Args:
            base_url: Alist服务地址
            username: 用户名
            password: 密码
            sync_delete_action: 同步删除动作("none"/"move"/"delete")
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.sync_delete_action = sync_delete_action.lower()
        self.sync_delete = self.sync_delete_action in ["move", "delete"]
        self.connection = self._create_connection()
        self.token = None

    def _create_connection(self) -> Union[http.client.HTTPConnection, http.client.HTTPSConnection]:
        """创建HTTP(S)连接"""
        match = re.match(r"(?:http[s]?://)?([^:/]+)(?::(\d+))?", self.base_url)
        if not match:
            raise ValueError("Invalid base URL format")
        
        host = match.group(1)
        port_part = match.group(2)
        port = int(port_part) if port_part else (443 if self.base_url.startswith("https://") else 80)
        
        return (http.client.HTTPSConnection(host, port) 
                if self.base_url.startswith("https://") 
                else http.client.HTTPConnection(host, port))

    def _make_request(self, method: str, path: str, headers: Dict = None, 
                     payload: str = None) -> Optional[Dict]:
        """发送HTTP请求并返回JSON响应"""
        try:
            self.connection.request(method, path, body=payload, headers=headers)
            response = self.connection.getresponse()
            return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return None

    def login(self) -> bool:
        """登录并获取token"""
        payload = json.dumps({"username": self.username, "password": self.password})
        headers = {
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json"
        }
        response = self._make_request("POST", "/api/auth/login", headers, payload)
        if response and response.get("data", {}).get("token"):
            self.token = response["data"]["token"]
            return True
        logger.error("获取token失败")
        return False

    def _directory_operation(self, operation: str, **kwargs) -> Optional[Dict]:
        """执行目录操作"""
        if not self.token:
            if not self.login():
                return None
                
        headers = {
            "Authorization": self.token,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json"
        }
        payload = json.dumps(kwargs)
        path = f"/api/fs/{operation}"
        return self._make_request("POST", path, headers, payload)

    def get_directory_contents(self, directory_path: str) -> List[Dict]:
        """获取目录内容"""
        response = self._directory_operation("list", path=directory_path)
        return response.get("data", {}).get("content", []) if response else []

    def create_directory(self, directory_path: str) -> bool:
        """创建目录"""
        response = self._directory_operation("mkdir", path=directory_path)
        if response:
            logger.info(f"文件夹【{directory_path}】创建成功")
            return True
        logger.error("文件夹创建失败")
        return False

    def copy_item(self, src_dir: str, dst_dir: str, item_name: str) -> bool:
        """复制文件或目录"""
        response = self._directory_operation("copy", 
                                          src_dir=src_dir, 
                                          dst_dir=dst_dir, 
                                          names=[item_name])
        if response:
            logger.info(f"文件【{item_name}】复制成功")
            return True
        logger.error("文件复制失败")
        return False

    def move_item(self, src_dir: str, dst_dir: str, item_name: str) -> bool:
        """移动文件或目录"""
        response = self._directory_operation("move", 
                                          src_dir=src_dir, 
                                          dst_dir=dst_dir, 
                                          names=[item_name])
        if response:
            logger.info(f"文件从【{src_dir}/{item_name}】移动到【{dst_dir}/{item_name}】移动成功")
            return True
        logger.error("文件移动失败")
        return False

    def is_path_exists(self, path: str) -> bool:
        """检查路径是否存在"""
        response = self._directory_operation("get", path=path)
        return bool(response and response.get("message") == "success")

    def get_storage_list(self) -> List[str]:
        """获取存储列表"""
        if not self.token:
            if not self.login():
                return []
                
        headers = {
            "Authorization": self.token,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json"
        }
        response = self._make_request("GET", "/api/admin/storage/list", headers)
        if response:
            storage_list = response["data"]["content"]
            return [item["mount_path"] for item in storage_list]
        logger.error("获取存储列表失败")
        return []

    def sync_directories(self, src_dir: str, dst_dir: str) -> bool:
        """同步两个目录"""
        try:
            if not self.is_path_exists(dst_dir):
                if not self.create_directory(dst_dir):
                    return False
            return self._recursive_copy(src_dir, dst_dir)
        except Exception as e:
            logger.error(f"同步目录失败: {e}")
            return False

    def _recursive_copy(self, src_dir: str, dst_dir: str) -> bool:
        """递归复制目录内容"""
        try:
            src_contents = self.get_directory_contents(src_dir)
            if not src_contents:
                return True

            if self.sync_delete:
                self._handle_sync_delete(src_dir, dst_dir, src_contents)

            for item in src_contents:
                if not self._copy_item_with_check(src_dir, dst_dir, item):
                    return False
            return True
        except Exception as e:
            logger.error(f"递归复制失败: {e}")
            return False

    def _handle_sync_delete(self, src_dir: str, dst_dir: str, src_contents: List[Dict]):
        """处理同步删除逻辑"""
        dst_contents = self.get_directory_contents(dst_dir)
        src_names = {item["name"] for item in src_contents}
        dst_names = {item["name"] for item in dst_contents}
        
        to_delete = dst_names - src_names
        if not to_delete:
            return

        for name in to_delete:
            if self.sync_delete_action == "move":
                trash_dir = self._get_trash_dir(dst_dir)
                if trash_dir:
                    if not self.is_path_exists(trash_dir):
                        self.create_directory(trash_dir)
                    self.move_item(dst_dir, trash_dir, name)
            else:  # delete
                self._directory_operation("remove", dir=dst_dir, names=[name])

    def _get_trash_dir(self, dst_dir: str) -> Optional[str]:
        """获取回收站目录路径"""
        storage_list = self.get_storage_list()
        for mount_path in storage_list:
            if dst_dir.startswith(mount_path):
                return f"{mount_path}/trash{dst_dir[len(mount_path):]}"
        return None

    def close(self):
        """关闭连接"""
        if self.connection:
            self.connection.close()




def main():
    """主函数，用于命令行执行"""
    # 从环境变量获取配置
    base_url = os.environ.get("BASE_URL")
    username = os.environ.get("USERNAME")
    password = os.environ.get("PASSWORD")
    sync_delete_action = os.environ.get("SYNC_DELETE_ACTION", "none")
    
    if not all([base_url, username, password]):
        logger.error("必要的环境变量未设置")
        return

    # 创建AlistSync实例
    alist_sync = AlistSync(base_url, username, password, sync_delete_action)
    
    try:
        # 获取同步目录对
        dir_pairs = get_dir_pairs_from_env()
        
        # 执行同步
        for pair in dir_pairs:
            src_dir, dst_dir = pair.split(":")
            alist_sync.sync_directories(src_dir.strip(), dst_dir.strip())
    finally:
        alist_sync.close()

def get_dir_pairs_from_env() -> List[str]:
    """从环境变量获取目录对列表"""
    dir_pairs_list = []
    
    # 获取主DIR_PAIRS
    if dir_pairs := os.environ.get("DIR_PAIRS"):
        dir_pairs_list.extend(dir_pairs.split(";"))
    
    # 获取DIR_PAIRS1到DIR_PAIRS50
    for i in range(1, 51):
        if dir_pairs := os.environ.get(f"DIR_PAIRS{i}"):
            dir_pairs_list.extend(dir_pairs.split(";"))
    
    return dir_pairs_list

if __name__ == '__main__':
    main()