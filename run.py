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
from server.services.text2video import start_video_service, stop_video_service
from server.services.action_dispatcher import start_action_dispatcher, stop_action_dispatcher
from warehouse.api import RecentUIDTracker

# 全局变量用于进程管理
processes = {}
stop_event = multiprocessing.Event()

def start_process(name, command, cwd=None):
    """启动子进程并返回其进程对象"""
    print(f"启动 {name}...")
    
    if cwd:
        process = multiprocessing.Process(
            target=start_video_service if name == "text2video_service" else start_action_dispatcher,
            args=(),
            kwargs={},
            daemon=True
        )
    else:
        process = multiprocessing.Process(
            target=start_video_service if name == "text2video_service" else start_action_dispatcher,
            args=(),
            kwargs={},
            daemon=True
        )
    
    processes[name] = process
    
    # 启动线程读取输出
    # threading.Thread(target=read_output, args=(process.stdout, f"{name} [OUT]"), daemon=True).start()
    # threading.Thread(target=read_output, args=(process.stderr, f"{name} [ERR]"), daemon=True).start()
    
    return process

def read_output(pipe, prefix):
    """读取管道输出并打印带有前缀"""
    for line in pipe:
        print(f"{prefix}: {line.strip()}")

def stop_all_processes():
    """停止所有正在运行的进程"""
    print("停止所有进程...")
    
    for name, process in processes.items():
        if process.is_alive():  # 进程仍在运行
            print(f"终止 {name}...")
            if name == "text2video_service":
                stop_video_service()
            elif name == "action_dispatcher":
                stop_action_dispatcher()
    
    # 等待进程终止
    time.sleep(1)
    
    # 强制杀死任何剩余的进程
    for name, process in processes.items():
        if process.is_alive():  # 进程仍在运行
            print(f"杀死 {name}...")
            process.terminate()

def signal_handler(sig, frame):
    """处理终止信号"""
    print(f"接收到信号 {sig}")
    stop_event.set()
    stop_all_processes()
    sys.exit(0)

def main():
    """主函数，启动所有组件"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建必要的目录
    os.makedirs("warehouse/text_data", exist_ok=True)
    os.makedirs("tasks", exist_ok=True)
    os.makedirs("tasks/conditions", exist_ok=True)
    os.makedirs("video_pool", exist_ok=True)
    
    # 初始化数据源跟踪器
    RecentUIDTracker()
    logger.info("数据源跟踪器已初始化")
    
    try:
        # 启动文本到视频服务
        text2video_service = start_process(
            "text2video_service",
            [],
            cwd=None
        )
        
        # 启动动作调度服务
        action_dispatcher = start_process(
            "action_dispatcher",
            [],
            cwd=None
        )
        
        print("所有服务启动。按 Ctrl+C 停止。")
        
        # 等待进程完成或终止信号
        while not stop_event.is_set():
            # 检查是否有进程意外终止
            for name, process in list(processes.items()):
                if not process.is_alive():
                    print(f"{name} 退出")
                    
                    # if exit_code != 0:
                    #     print(f"重新启动 {name}...")
                    #     if name == "warehouse_api":
                    #         start_process("warehouse_api", ["python", "api.py"], cwd="warehouse")
                    #     elif name == "server_api":
                    #         start_process("server_api", ["python", "api.py"], cwd="server")
                    #     elif name == "text2video_service":
                    #         start_process("text2video_service", ["python", "-c", "from server.text2video import start_text2video_service; start_text2video_service(); import time; import signal; signal.pause()"])
                    #     elif name == "action_dispatcher":
                    #         start_process("action_dispatcher", ["python", "-c", "from server.action_dispatcher import start_action_dispatcher; start_action_dispatcher(); import time; import signal; signal.pause()"])
                    
                    del processes[name]
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("键盘中断接收")
    finally:
        stop_event.set()
        stop_all_processes()

if __name__ == "__main__":
    main()
