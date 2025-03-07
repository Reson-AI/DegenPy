#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import signal
import logging
import multiprocessing
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run")

# 导入服务组件
from server.agents.engine import agent_engine

# 全局变量用于进程管理
processes = {}
stop_event = multiprocessing.Event()

def start_process(name, target_func, args=(), kwargs={}):
    """启动子进程并返回其进程对象"""
    logger.info(f"启动 {name}...")
    
    process = multiprocessing.Process(
        target=target_func,
        args=args,
        kwargs=kwargs,
        daemon=True
    )
    
    process.start()
    processes[name] = process
    return process

def stop_all_processes():
    """停止所有正在运行的进程"""
    logger.info("停止所有进程...")
    
    for name, process in processes.items():
        if process.is_alive():  # 进程仍在运行
            logger.info(f"终止 {name}...")
            process.terminate()
    
    # 等待进程终止
    time.sleep(1)

def signal_handler(sig, frame):
    """处理终止信号"""
    logger.info(f"接收到信号 {sig}")
    stop_event.set()
    stop_all_processes()
    sys.exit(0)

def start_server_api():
    """启动Server API服务器"""
    import uvicorn
    from server.api import app
    
    # 启动API服务器
    uvicorn.run(app, host="0.0.0.0", port=8001)

def start_warehouse_api():
    """启动Warehouse API服务器"""
    import uvicorn
    from warehouse.api import app
    
    # 启动API服务器
    uvicorn.run(app, host="0.0.0.0", port=8000)

def main():
    """主函数，启动所有组件"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建必要的目录
    os.makedirs("warehouse/text_data", exist_ok=True)
    os.makedirs("tasks", exist_ok=True)
    os.makedirs("video_pool", exist_ok=True)
    
    # 不在这里启动agent，而是由server/api服务管理
    logger.info("由server/api服务管理agent启动...")
    
    # 启动Warehouse API服务器
    warehouse_api = start_process(
        "warehouse_api",
        target_func=start_warehouse_api
    )
    
    # 启动Server API服务器
    server_api = start_process(
        "server_api",
        target_func=start_server_api
    )
    
    try:
        logger.info("所有服务启动完成。按 Ctrl+C 停止。")
        
        # 等待进程完成或终止信号
        while not stop_event.is_set():
            # 检查是否有进程意外终止
            for name, process in list(processes.items()):
                if not process.is_alive():
                    logger.warning(f"{name} 意外退出，尝试重新启动...")
                    
                    if name == "warehouse_api":
                        start_process("warehouse_api", start_warehouse_api)
                    elif name == "server_api":
                        start_process("server_api", start_server_api)
                    
                    del processes[name]
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("接收到键盘中断")
    finally:
        stop_event.set()
        stop_all_processes()

if __name__ == "__main__":
    main()
