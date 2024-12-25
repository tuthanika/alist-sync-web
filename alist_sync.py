import http.client  # 用于创建HTTP或HTTPS连接，进行网络请求相关操作
import json  # 用于处理JSON数据格式的解析和序列化
import re  # 利用正则表达式进行字符串匹配、解析等操作
from apscheduler.schedulers.background import BackgroundScheduler  # 创建后台任务调度器
from apscheduler.triggers.cron import CronTrigger  # 定义基于Cron表达式的任务触发规则
import time  # 用于处理时间相关操作，如休眠等
from datetime import datetime, timedelta  # 处理日期和时间的计算、格式化等
import os  # 与操作系统环境交互，获取环境变量等
import logging  # 配置和记录日志信息

# 配置日志记录器
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# 解析命令行参数
base_url = os.environ.get("BASE_URL")
username = os.environ.get("USERNAME")
password = os.environ.get("PASSWORD")
cron_schedule = os.environ.get("CRON_SCHEDULE")

sync_delete_action = os.environ.get("SYNC_DELETE_ACTION", "none").lower()
sync_delete = sync_delete_action == "move" or sync_delete_action == "delete"

if cron_schedule:
    # 创建一个后台调度器实例
    scheduler = BackgroundScheduler()

    # 创建一个CronTrigger实例
    trigger = CronTrigger.from_crontab(cron_schedule)


def xiaojin():
    """
    打印一段特定格式的文本，可能用于标识或提示相关信息。
    """
    pt = """

                                 ..
                                ....                       
                             .:----=:                      
                    ...:::---==-:::-+.                     
                ..:=====-=+=-::::::==             .:-.   
            .-==*=-:::::::::::::::=*-:         .:-=++.   
         .-==++++-::::::::::::::-++:-==:.     .=-=::=-.  
 ....:::-=-::-++-:::::::::::::::--:::::==:      -:.:=..+:  
  ==-------::::-==-:::::::::::::::::::::::-+-..=: .:=-.. 
  ==-::::+-:::::==-:::::::::::::::::::::::::=+.:+-    :-:    
   :--==+*::::::-=-::::::::::::::::::::::::::-*+:  .+.     
    ..-*:::::::==::::::::::::::::::::::::::-+.     -+.     
        -*:::::::-=-:::::::--:::::::::::::::=-.      +-      
        :*::::::::-=::::::-=:::::-*-::......::        --       
         :+::-:::::::::::::::::*=:-::......         -.       
          :-:-===-:::::::::::.:+==--:......      .+.       
      .==:...-+#+::....... .   .......       .=-       
        -*.....::............::-.               ...=-      
      .==-:..       :=-::::::=.                ..:+-     
        .:--===---=-:::-:::--:.                 ..:+:    
             =--+=:+*+:. ......                    ..-+.   
          .#..+#-.:.                           .::=:   
             -=:.-:                                ..::-.  
            .-=.               xjxjin            ...:-:  
             ...                                  ...:-  



    """
    logger.info(pt)


def get_dir_pairs_from_env():
    """
    从环境变量中获取目录对（DIR_PAIRS及DIR_PAIRS1 - DIR_PAIRS50等）的值，
    将获取到的非空目录对信息整理成列表并返回。
    """
    # 初始化列表来存储环境变量的值
    dir_pairs_list = []

    # 尝试从环境变量中获取DIR_PAIRS的值
    dir_pairs = os.environ.get("DIR_PAIRS")
    # 检查DIR_PAIRS是否不为空
    logger.info("本次同步目录有：")
    num = 1
    if dir_pairs:
        # 将DIR_PAIRS的值添加到列表中
        dir_pairs_list.append(dir_pairs)
        logger.info(f"No.{num:02d}【{dir_pairs}】")
        num += 1

    # 循环尝试获取DIR_PAIRS1到DIR_PAIRS50的值
    for i in range(1, 51):
        # 构造环境变量名
        env_var_name = f"DIR_PAIRS{i}"
        # 尝试获取环境变量的值
        env_var_value = os.environ.get(env_var_name)
        # 如果环境变量的值不为空，则添加到列表中
        if env_var_value:
            dir_pairs_list.append(env_var_value)
            logger.info(f"No.{num:02d}【{env_var_value}】")
            num += 1

    return dir_pairs_list


def create_connection(base_url):
    """
    根据给定的基础URL创建对应的HTTP或HTTPS连接。
    参数：
    - base_url: 表示目标服务器的基础URL地址。
    返回值：
    - 返回创建好的HTTPConnection或HTTPSConnection对象实例，用于后续发送请求。
    """
    # 使用正则表达式解析URL，获取主机名和端口
    match = re.match(r"(?:http[s]?://)?([^:/]+)(?::(\d+))?", base_url)
    host = match.group(1)
    port_part = match.group(2)
    port = int(port_part) if port_part else (80 if "http://" in base_url else 443)

    # 根据URL的协议类型创建HTTP或HTTPS连接
    return http.client.HTTPSConnection(host, port) if base_url.startswith("https://") else http.client.HTTPConnection(
        host, port)


def make_request(connection, method, path, headers=None, payload=None):
    """
    发送HTTP请求并返回JSON解析后的响应内容。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - method: 请求方法，如'GET'、'POST'等。
    - path: 请求的路径地址。
    - headers: 请求头信息（可选）。
    - payload: 请求体内容（可选）。
    返回值：
    - 如果请求成功，返回解析后的JSON响应内容；如果请求失败，返回None并记录错误日志。
    """
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"请求失败: {e}")
        return None


def get_token(connection, path, username, password):
    """
    获取认证token。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - path: 认证请求的路径地址。
    - username: 用户名。
    - password: 密码。
    返回值：
    - 如果获取成功，返回token信息；如果失败，返回None并记录获取token失败的错误日志。
    """
    payload = json.dumps({"username": username, "password": password})
    headers = {
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Content-Type": "application/json"
    }
    response = make_request(connection, "POST", path, headers, payload)
    if response:
        return response["data"]["token"]
    else:
        logger.error("获取token失败")
        return None


def directory_operation(connection, token, operation, **kwargs):
    """
    一个通用函数，用于执行目录操作。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - operation: 操作类型，如'mkdir'、'list'、'copy'等。
    - **kwargs: 其他与操作相关的参数，根据具体操作而定，例如创建目录时传入目录路径等。
    返回值：
    - 返回对应操作的响应内容，如果请求失败返回None。
    """
    headers = {
        "Authorization": token,
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Content-Type": "application/json"
    }
    payload = json.dumps(kwargs)
    path = f"/api/fs/{operation}"  # 构建API路径
    response = make_request(connection, "POST", path, headers, payload)
    return response


def get_directory_contents(connection, token, directory_path):
    """
    获取目录下的文件和文件夹列表。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - directory_path: 要获取内容的目录路径。
    返回值：
    - 返回包含文件和文件夹信息的字典中的 'content' 列表，如果请求失败返回空列表。
    """
    return directory_operation(connection, token, "list", path=directory_path).get("data", [])


def create_directory(connection, token, directory_path):
    """
    创建新文件夹。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - directory_path: 要创建的文件夹路径。
    """
    response = directory_operation(connection, token, "mkdir", path=directory_path)
    if response:
        logger.info(f"文件夹【{directory_path}】创建成功")
    else:
        logger.error("文件夹创建失败")


def copy_item(connection, token, src_dir, dst_dir, item_name):
    """
    复制文件或文件夹。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - src_dir: 源文件或文件夹所在的目录路径。
    - dst_dir: 目标目录路径。
    - item_name: 要复制的文件或文件夹的名称。
    """
    response = directory_operation(connection, token, "copy", src_dir=src_dir, dst_dir=dst_dir, names=[item_name])
    if response:
        logger.info(f"文件【{item_name}】复制成功")
    else:
        logger.error("文件复制失败")


def move_item(connection, token, src_dir, dst_dir, item_name):
    """
    移动文件或文件夹。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - src_dir: 源文件或文件夹所在的目录路径。
    - dst_dir: 目标目录路径。
    - item_name: 要移动的文件或文件夹的名称。
    """
    response = directory_operation(connection, token, "move", src_dir=src_dir, dst_dir=dst_dir, names=[item_name])
    if response:
        logger.info(f"文件从【{src_dir}/{item_name}】移动到【{dst_dir}/{item_name}】移动成功")
    else:
        logger.error("文件移动失败")


def is_path_exists(connection, token, path):
    """
    判断路径是否存在，包括文件和文件夹。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - path: 要判断存在性的路径地址。
    返回值：
    - 如果路径存在，返回True；否则返回False。
    """
    response = directory_operation(connection, token, "get", path=path)
    return response and response.get("message", "") == "success"


def is_directory_size(connection, token, directory_path):
    """
    获取指定目录的文件大小信息（此处原代码逻辑可能不太准确，可根据实际情况完善，当前按原逻辑注释说明）。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - directory_path: 要获取文件大小的目录路径。
    返回值：
    - 返回目录相关的文件大小信息，具体根据响应数据结构而定（原代码返回['data']['size']）。
    """
    response = directory_operation(connection, token, "get", path=directory_path)
    return response["data"]["size"]


def is_directory_modified_date(connection, token, directory_path):
    """
    获取指定目录的文件修改时间信息（此处原代码逻辑可能不太准确，可根据实际情况完善，当前按原逻辑注释说明）。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - directory_path: 要获取文件修改时间的目录路径。
    返回值：
    - 返回目录相关的文件修改时间信息，具体根据响应数据结构而定（原代码返回['data']['modified']）。
    """
    response = directory_operation(connection, token, "get", path=directory_path)
    return response["data"]["modified"]


def directory_remove(connection, token, directory_path, file_name):
    """
    删除指定目录下的文件。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    - directory_path: 文件所在的目录路径。
    - file_name: 要删除的文件名称。
    """
    response = directory_operation(connection, token, "remove", dir=directory_path, names=[file_name])
    if response.get("message", "") == "success":
        logger.info(f"文件【{directory_path}/{file_name}】删除成功")
    else:
        logger.error(f"文件【{directory_path}/{file_name}】删除失败")


def get_storage_list(connection, token):
    """
    列出存储列表。
    参数：
    - connection: 已经创建好的HTTP或HTTPS连接对象。
    - token: 认证token。
    返回值：
    - 返回存储列表中的挂载路径信息列表，如果获取失败返回None并记录错误日志。
    """
    headers = {
        "Authorization": token,
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Content-Type": "application/json"
    }
    response = make_request(connection, "GET", "/api/admin/storage/list", headers)
    if response:
        storage_list = response["data"]["content"]
        return [list["mount_path"] for list in storage_list]
    else:
        logger.error("获取存储列表失败")
        return None


def parse_time_and_adjust_utc(date_str):
    """
    使用正则表达式解析时间字符串，如果是UTC格式（包含'Z'）则加8小时。
    参数：
    - date_str: 表示时间的字符串，格式类似 "2024-12-09T13:17:45.82Z" 或者 "2024-12-09T21:17:28.179+08:00" 等格式。
    返回值：
    - 返回解析并调整时区后的datetime对象，如果匹配失败等情况返回None（可根据实际需求完善错误处理）。
    """
    # 匹配ISO 8601格式类似 "2024-12-09T13:17:45.82Z" 或者 "2024-12-09T21:17:28.179+08:00" 等格式
    iso_8601_pattern = r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?([+-]\d{2}:\d{2}|Z)?'
    match_iso = re.match(iso_8601_pattern, date_str)
    if match_iso:
        year, month, day, hour, minute, second, microsecond, timezone = match_iso.groups()
        if microsecond:
            microsecond = int(float(microsecond) * 1000000)  # 将小数形式的微秒转换为整数
        else:
            microsecond = 0
        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), microsecond)
        if timezone == "Z":
            dt = dt + timedelta(hours=8)  # 如果是UTC时间，增加8小时
        elif timezone:
            # 处理其他时区偏移量（这里暂简单处理时区转换，实际可能更复杂）
            sign = 1 if timezone[0] == "+" else -1
            hours = int(timezone[1:3])
            minutes = int(timezone[4:6])
            offset = timedelta(hours=sign * hours, minutes=sign * minutes)
            dt = dt - offset
        return dt


def recursive_copy(src_dir, dst_dir, connection, token, sync_delete=False):
    """
    递归地复制源目录（src_dir）下的文件和文件夹到目标目录（dst_dir）。
    参数：
    - src_dir: 源目录的路径，表示要复制的内容所在的起始目录。
    - dst_dir: 目标目录的路径，复制的内容将被放置到该目录下。
    - connection: 已经创建好的HTTP或HTTPS连接对象，用于与服务器通信。
    - token: 认证token，用于在请求中进行身份验证。
    - sync_delete: 布尔值，表示是否启用同步删除功能，即处理目标目录中多余文件的删除或移动操作（默认值为False）。
    """
    global dst_contents
    try:
        src_contents = get_directory_contents(connection, token, src_dir)["content"]
    except Exception as e:
        logger.error(f"获取目录【{src_dir}】失败: {e}")
        return
    # 空目录跳过
    if not src_contents:
        return

    # 因为开启了递归，所以需要先判断源目录是否存在多余文件，来确定是否移动或者删除文件
    # 如果启用了同步删除，删除目标目录中不存在于源目录的文件
    if sync_delete:
        dst_list = []
        try:
            dst_contents = get_directory_contents(connection, token, dst_dir)["content"]
            for dst_item in dst_contents:
                item_name = dst_item["name"]
                dst_list.append(item_name)
        except Exception as e:
            logger.error(f"获取目录【{dst_dir}】失败: {e}")

        src_list = []
        for item in src_contents:
            item_name = item["name"]
            # 添加源目录下文件名称
            src_list.append(item_name)

        # 获取目标目录有的文件，但是源目录没有的文件
        diff_list = list(set(dst_list) - set(src_list))
        if len(diff_list) > 0:
            for dst_item in dst_contents:
                item_name = dst_item["name"]

                if item_name in diff_list:
                    # 如果是移动判断源文件夹是否存在
                    if sync_delete_action == "move":
                        # 拼接移动文件路径
                        # 拼接到目标目录的trash下，获取文件夹所在的存储路径名称,拼接移动文件路径
                        trash_dir = ""
                        storage_list = get_storage_list(connection, token)
                        for mount_path in storage_list:
                            if dst_dir.startswith(mount_path):
                                c = dst_dir[len(mount_path):]
                                trash_dir = f"{mount_path}/trash{c}"
                                break

                        # 判断文件夹是否存在，不存在就创建文件夹
                        if not is_path_exists(connection, token, trash_dir):
                            create_directory(connection, token, trash_dir)
                        move_item(connection, token, dst_dir, trash_dir, item_name)

                    if sync_delete_action == "delete":
                        directory_remove(connection, token, dst_dir, item_name)

    # 开始复制文件操作
    for item in src_contents:
        item_name = item["name"]
        item_path = f"{src_dir}/{item_name}"
        dst_item_path = f"{dst_dir}/{item_name}"

        # 添加源目录下文件名称
        if item["is_dir"]:
            if not is_path_exists(connection, token, dst_item_path):
                create_directory(connection, token, dst_item_path)
            else:
                logger.info(f"文件夹【{dst_item_path}】已存在，跳过创建")

            # 递归复制文件夹
            recursive_copy(item_path, dst_item_path, connection, token, sync_delete)
        else:
            if not is_path_exists(connection, token, dst_item_path):
                copy_item(connection, token, src_dir, dst_dir, item_name)
            else:
                src_size = item["size"]
                dst_size = is_directory_size(connection, token, dst_item_path)
                if src_size == dst_size:
                    logger.info(f"文件【{item_name}】已存在，跳过复制")
                else:
                    # 获取文件修改时间
                    src_modified_date = item["modified"]
                    dst_modified_date = is_directory_modified_date(connection, token, dst_item_path)
                    src_date = parse_time_and_adjust_utc(src_modified_date)
                    dst_date = parse_time_and_adjust_utc(dst_modified_date)

                    if dst_date > src_date:
                        logger.info(f"文件【{item_name}】目标文件修改时间晚于源文件，跳过复制")
                    else:
                        logger.info(f"文件【{item_name}】文件存在变更，删除文件")
                        directory_remove(connection, token, dst_dir, item_name)
                        copy_item(connection, token, src_dir, dst_dir, item_name)


def execute_sync_task():
    """
    执行同步任务的核心逻辑，包括创建连接、获取token、遍历目录对并进行递归复制等操作。
    """
    conn = create_connection(base_url)
    token = get_token(conn, "/api/auth/login", username, password)

    dir_pairs_list = get_dir_pairs_from_env()
    i = 0
    # 遍历dir_pairs_list中的每个值
    for value in dir_pairs_list:
        # 将当前遍历到的值赋给变量dir_pairs
        dir_pairs = value
        # 执行需要使用dir_pairs的代码
        # 例如，打印dir_pairs的值
        # logger.info(dir_pairs)

        data_list = dir_pairs.split(";")

        for item in data_list:
            i = i + 1
            pair = item.split(":")
            try:
                if len(pair) == 2:
                    src_dir, dst_dir = pair[0], pair[1]
                    logger.info(f"")
                    logger.info(f"")
                    logger.info(f"")
                    logger.info(f"")
                    logger.info(f"")
                    logger.info(f"第 [{i:02d}] 个 同步目录【{src_dir}】---->【 {dst_dir}】")
                    logger.info(f"")
                    logger.info(f"")
                    if not is_path_exists(conn, token, dst_dir):
                        create_directory(conn, token, dst_dir)

                    # logger.info(f"同步源目录: {src_dir}, 到目标目录: {dst_dir}")
                    recursive_copy(src_dir, dst_dir, conn, token, sync_delete)

                else:
                    logger.error(f"源目录或目标目录不存在: {item}")
            except Exception as e:
                logger.error(f"同步目录【{item}】失败: {e}")

    conn.close()


def main():
    """
    作为整个脚本的入口函数，根据环境变量中CRON_SCHEDULE的配置情况来决定同步任务的执行方式。
    如果CRON_SCHEDULE为空或为特定无效值，则执行一次同步任务，该同步任务包括了一系列操作，如打印标识信息、创建连接、获取token、
    从环境变量获取目录对信息并遍历执行递归复制等操作，最后关闭连接并记录同步结束信息。
    如果CRON_SCHEDULE有有效值，则按照Cron表达式配置的时间规则，将同步任务添加到后台调度器中定时执行，调度器会在后台线程运行，
    主线程会阻塞等待（通过循环休眠的方式），直到接收到中断信号（如用户按Ctrl+C），此时会关闭调度器。
    注意：在外部导入并调用该函数时，需要确保相关的环境变量（如BASE_URL、USERNAME、PASSWORD、CRON_SCHEDULE等）已经正确设置。
    """
    xiaojin()
    logger.info(f"同步任务运行开始 {datetime.now()}")
    if not cron_schedule or cron_schedule is None or cron_schedule == "None":
        # 执行一次同步任务核心逻辑
        execute_sync_task()
    else:
        # 创建调度器相关逻辑保持不变
        scheduler = BackgroundScheduler()
        trigger = CronTrigger.from_crontab(cron_schedule)
        scheduler.add_job(execute_sync_task, trigger=trigger)
        scheduler.start()
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
    logger.info(f"同步任务运行结束 {datetime.now()}")


if __name__ == '__main__':
    #... 解析命令行参数...

    # 检查CRON_SCHEDULE是否为空或者为null
    if not cron_schedule or cron_schedule is None or cron_schedule == "None":
        # logger.info("CRON_SCHEDULE为空，将执行一次同步任务。")
        main()  # 执行一次同步任务
    else:
        # 添加任务到调度器，使用创建的CronTrigger实例
        scheduler.add_job(main, trigger=trigger)

        # 开始调度器
        scheduler.start()
        try:
            # 这会阻塞主线程，但调度器在后台线程中运行
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            # 如果主线程被中断（例如用户按Ctrl+C），则关闭调度器
            scheduler.shutdown()