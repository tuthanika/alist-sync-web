import requests
import json
import logging
import base64
import hashlib
import hmac
import time
import urllib.parse
from flask import current_app

class Notifier:
    """
    通知模块，支持多种通知渠道
    """
    def __init__(self, settings=None):
        self.settings = settings or {}
        self.logger = logging.getLogger('notifier')
    
    def send_notification(self, title, content, task_info=None):
        """
        发送通知
        :param title: 通知标题
        :param content: 通知内容
        :param task_info: 任务相关信息
        """
        # 获取设置，如果没有初始化设置则尝试从应用配置获取
        if not self.settings and hasattr(current_app, 'config') and 'DATA_MANAGER' in current_app.config:
            data_manager = current_app.config['DATA_MANAGER']
            self.settings = data_manager.get_settings()
        
        # 检查是否启用了通知
        if not self.settings.get('enable_webhook', False):
            self.logger.debug("通知未启用")
            return False
        
        # 根据设置的通知类型发送通知
        notification_type = self.settings.get('notification_type', 'feishu')
        
        try:
            # 根据通知类型调用相应的方法
            if notification_type == 'feishu':
                return self.send_feishu(title, content, task_info)
            elif notification_type == 'dingtalk':
                return self.send_dingtalk(title, content, task_info)
            elif notification_type == 'wecom':
                return self.send_wecom(title, content, task_info)
            elif notification_type == 'bark':
                return self.send_bark(title, content, task_info)
            elif notification_type == 'pushplus':
                return self.send_pushplus(title, content, task_info)
            elif notification_type == 'telegram':
                return self.send_telegram(title, content, task_info)
            elif notification_type == 'webhook':
                return self.send_webhook(title, content, task_info)
            else:
                self.logger.error(f"不支持的通知类型: {notification_type}")
                return False
        except Exception as e:
            self.logger.error(f"发送通知失败: {str(e)}")
            return False
    
    def format_task_message(self, title, content, task_info):
        """格式化任务消息"""
        if not task_info:
            return {'title': title, 'content': content}
        
        task_name = task_info.get('name', '未命名任务')
        task_id = task_info.get('id', '未知ID')
        status = task_info.get('status', '未知状态')
        duration = task_info.get('duration', '未知')
        
        # 格式化为Markdown格式（适用于大部分平台）
        formatted_content = f"""
### {title}

**任务名称**: {task_name}
**任务ID**: {task_id}
**执行状态**: {status}
**执行时长**: {duration}

{content}
"""
        return {'title': title, 'content': formatted_content}
    
    def send_feishu(self, title, content, task_info=None):
        """发送飞书通知"""
        webhook_url = self.settings.get('webhook_url', '')
        if not webhook_url:
            self.logger.error("飞书 Webhook URL 未设置")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # 飞书卡片消息格式
        message = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": formatted['title']
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": formatted['content']
                        }
                    }
                ]
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    self.logger.info("飞书通知发送成功")
                    return True
                else:
                    self.logger.error(f"飞书通知发送失败: {result.get('msg')}")
                    return False
            else:
                self.logger.error(f"飞书通知HTTP错误: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"发送飞书通知时出错: {str(e)}")
            return False
    
    def send_dingtalk(self, title, content, task_info=None):
        """发送钉钉通知"""
        webhook_url = self.settings.get('webhook_url', '')
        secret = self.settings.get('dingtalk_secret', '')
        
        if not webhook_url:
            self.logger.error("钉钉 Webhook URL 未设置")
            return False
        
        # 如果有加签秘钥，需要计算签名
        if secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            signature = base64.b64encode(
                hmac.new(
                    secret.encode('utf-8'),
                    string_to_sign.encode('utf-8'),
                    digestmod=hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={urllib.parse.quote_plus(signature)}"
        
        formatted = self.format_task_message(title, content, task_info)
        
        # 钉钉消息格式
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": formatted['title'],
                "text": formatted['content']
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    self.logger.info("钉钉通知发送成功")
                    return True
                else:
                    self.logger.error(f"钉钉通知发送失败: {result.get('errmsg')}")
                    return False
            else:
                self.logger.error(f"钉钉通知HTTP错误: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"发送钉钉通知时出错: {str(e)}")
            return False
    
    def send_wecom(self, title, content, task_info=None):
        """发送企业微信通知"""
        webhook_url = self.settings.get('webhook_url', '')
        
        if not webhook_url:
            self.logger.error("企业微信 Webhook URL 未设置")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # 企业微信消息格式
        message = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"# {formatted['title']}\n{formatted['content']}"
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    self.logger.info("企业微信通知发送成功")
                    return True
                else:
                    self.logger.error(f"企业微信通知发送失败: {result.get('errmsg')}")
                    return False
            else:
                self.logger.error(f"企业微信通知HTTP错误: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"发送企业微信通知时出错: {str(e)}")
            return False
    
    def send_bark(self, title, content, task_info=None):
        """发送Bark通知"""
        bark_url = self.settings.get('webhook_url', '')
        bark_sound = self.settings.get('bark_sound', 'default')
        
        if not bark_url:
            self.logger.error("Bark URL 未设置")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # 构造Bark URL
        # 如果URL不以/结尾，添加/
        if not bark_url.endswith('/'):
            bark_url += '/'
        
        # 编码标题和内容
        encoded_title = urllib.parse.quote_plus(formatted['title'])
        encoded_content = urllib.parse.quote_plus(formatted['content'])
        
        # 构造完整的Bark URL
        full_url = f"{bark_url}{encoded_title}/{encoded_content}?sound={bark_sound}"
        
        try:
            response = requests.get(full_url)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    self.logger.info("Bark通知发送成功")
                    return True
                else:
                    self.logger.error(f"Bark通知发送失败: {result.get('message')}")
                    return False
            else:
                self.logger.error(f"Bark通知HTTP错误: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"发送Bark通知时出错: {str(e)}")
            return False
    
    def send_pushplus(self, title, content, task_info=None):
        """发送PushPlus通知"""
        token = self.settings.get('webhook_url', '')
        
        if not token:
            self.logger.error("PushPlus Token 未设置")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # PushPlus接口
        api_url = "http://www.pushplus.plus/send"
        
        data = {
            "token": token,
            "title": formatted['title'],
            "content": formatted['content'],
            "template": "markdown"
        }
        
        try:
            response = requests.post(
                api_url,
                data=json.dumps(data),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    self.logger.info("PushPlus通知发送成功")
                    return True
                else:
                    self.logger.error(f"PushPlus通知发送失败: {result.get('msg')}")
                    return False
            else:
                self.logger.error(f"PushPlus通知HTTP错误: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"发送PushPlus通知时出错: {str(e)}")
            return False
    
    def send_telegram(self, title, content, task_info=None):
        """发送Telegram通知"""
        bot_token = self.settings.get('telegram_bot_token', '')
        chat_id = self.settings.get('telegram_chat_id', '')
        
        if not bot_token or not chat_id:
            self.logger.error("Telegram配置不完整: 需要bot_token和chat_id")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # Telegram Bot API
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # 合并标题和内容
        message_text = f"*{formatted['title']}*\n\n{formatted['content']}"
        
        data = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(api_url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    self.logger.info("Telegram通知发送成功")
                    return True
                else:
                    self.logger.error(f"Telegram通知发送失败: {result.get('description')}")
                    return False
            else:
                self.logger.error(f"Telegram通知HTTP错误: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"发送Telegram通知时出错: {str(e)}")
            return False
    
    def send_webhook(self, title, content, task_info=None):
        """发送自定义Webhook通知"""
        webhook_url = self.settings.get('webhook_url', '')
        
        if not webhook_url:
            self.logger.error("Webhook URL 未设置")
            return False
        
        formatted = self.format_task_message(title, content, task_info)
        
        # 构造通用Webhook格式
        payload = {
            "title": formatted['title'],
            "content": formatted['content'],
            "task_info": task_info
        }
        
        try:
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload)
            )
            
            if 200 <= response.status_code < 300:
                self.logger.info("Webhook通知发送成功")
                return True
            else:
                self.logger.error(f"Webhook通知HTTP错误: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"发送Webhook通知时出错: {str(e)}")
            return False 