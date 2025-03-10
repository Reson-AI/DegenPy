import os
import json
import time
import threading
import logging
from dotenv import load_dotenv

# 尝试导入redis，如果不可用则设置标志位
REDIS_AVAILABLE = True
try:
    import redis
except ImportError:
    REDIS_AVAILABLE = False
    logging.getLogger("root").warning("Redis模块导入失败，将禁用消息队列功能")

# 检查是否需要实际使用消息队列
USE_MESSAGE_QUEUE = os.getenv('USE_MESSAGE_QUEUE', 'false').lower() == 'true'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("message_queue")

# 加载环境变量
load_dotenv()

class MessageQueue:
    def __init__(self):
        # 如果Redis模块不可用或者不需要使用消息队列，直接设置为未连接状态
        if not REDIS_AVAILABLE:
            logger.warning("Redis模块不可用，无法初始化消息队列")
            self.connected = False
            self.redis = None
            return
            
        if not USE_MESSAGE_QUEUE:
            logger.info("消息队列功能已禁用 (USE_MESSAGE_QUEUE=false)")
            self.connected = False
            self.redis = None
            return
            
        try:
            # 使用环境变量中的Redis配置
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_password = os.getenv('REDIS_PASSWORD', '')
            redis_db = int(os.getenv('REDIS_DB', 0))
            redis_prefix = os.getenv('REDIS_PREFIX', 'degenpy:')
            
            logger.info(f"尝试连接到Redis: {redis_host}:{redis_port}")
            
            # 建立连接
            self.redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password if redis_password else None,
                db=redis_db,
                decode_responses=True
            )
            
            # 测试连接
            self.redis.ping()
            
            # 设置队列前缀
            self.queue_prefix = redis_prefix + 'queue:'
            self.subscribers = {}
            self.running = True
            
            logger.info("成功连接到Redis服务器，消息队列功能已启用")
            self.connected = True
        except redis.exceptions.ConnectionError as e:
            logger.error(f"无法连接到Redis服务器: {str(e)}")
            logger.warning("请确保Redis服务器已安装并运行，或者设置USE_MESSAGE_QUEUE=false来禁用消息队列功能")
            self.connected = False
            self.redis = None
        except Exception as e:
            logger.error(f"初始化消息队列时出错: {str(e)}")
            self.connected = False
            self.redis = None

    def publish(self, queue_name, message):
        """使用Redis列表实现消息发布"""
        if not self.connected or self.redis is None:
            logger.warning("消息队列未连接，无法发布消息")
            return False
            
        try:
            # 将消息添加到Redis列表末尾
            full_queue_name = self.queue_prefix + queue_name
            self.redis.rpush(full_queue_name, json.dumps(message))
            
            # 如果使用了发布/订阅模式，也发布一条通知
            self.redis.publish(full_queue_name + ':notify', 'new_message')
            
            logger.debug(f"消息已发布到队列 {queue_name}")
            return True
        except Exception as e:
            logger.error(f"发布消息时出错: {str(e)}")
            return False

    def consume(self, queue_name, callback):
        """使用Redis列表实现消息消费"""
        if not self.connected or self.redis is None:
            logger.warning("消息队列未连接，无法消费消息")
            return False
            
        full_queue_name = self.queue_prefix + queue_name
        
        # 创建一个消费者线程
        def consumer_thread():
            logger.info(f"开始消费队列 {queue_name} 的消息")
            while self.running:
                try:
                    # 使用阻塞式获取消息，超时时间为1秒
                    result = self.redis.blpop([full_queue_name], timeout=1)
                    if result:
                        _, message_data = result
                        try:
                            # 解析消息并调用回调函数
                            message = json.loads(message_data)
                            callback(None, None, None, message)
                        except json.JSONDecodeError:
                            logger.error(f"解析消息失败: {message_data}")
                        except Exception as e:
                            logger.error(f"处理消息时出错: {str(e)}")
                except Exception as e:
                    logger.error(f"消费消息时出错: {str(e)}")
                    time.sleep(1)  # 出错时暂停一下，避免CPU占用过高
            
            logger.info(f"停止消费队列 {queue_name} 的消息")
        
        # 启动消费者线程
        thread = threading.Thread(
            target=consumer_thread, 
            name=f"Redis-Consumer-{queue_name}",
            daemon=True
        )
        thread.start()
        
        # 保存订阅信息
        self.subscribers[queue_name] = thread
        return True
            
    def close(self):
        """关闭消息队列连接"""
        if self.connected and self.redis:
            try:
                # 停止所有消费者线程
                self.running = False
                
                # 等待所有线程结束（最多等待3秒）
                for name, thread in self.subscribers.items():
                    if thread.is_alive():
                        thread.join(timeout=3)
                
                # 清空订阅者列表
                self.subscribers.clear()
                
                # Redis连接池会自动管理连接，不需要显式关闭
                logger.info("已关闭Redis消息队列连接")
            except Exception as e:
                logger.error(f"关闭消息队列连接时出错: {str(e)}")
