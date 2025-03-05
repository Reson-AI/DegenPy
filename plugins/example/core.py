#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
示例插件核心功能
"""

import time
from typing import Dict, Any, List, Optional

class ExampleTool:
    """示例工具类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化示例工具
        
        参数:
            config: 可选的配置字典
        """
        self.config = config or {}
        self.name = "ExampleTool"
        self.initialized_time = time.time()
    
    def process_data(self, data: Any) -> Dict[str, Any]:
        """
        处理数据的示例方法
        
        参数:
            data: 要处理的数据
            
        返回:
            处理结果
        """
        return {
            "original": data,
            "processed": f"已处理: {data}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tool": self.name
        }
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取工具信息
        
        返回:
            工具信息字典
        """
        return {
            "name": self.name,
            "initialized_at": time.strftime("%Y-%m-%d %H:%M:%S", 
                                           time.localtime(self.initialized_time)),
            "config": self.config
        }

def get_example_data() -> List[Dict[str, Any]]:
    """
    获取示例数据
    
    返回:
        示例数据列表
    """
    return [
        {"id": 1, "name": "示例1", "value": 100},
        {"id": 2, "name": "示例2", "value": 200},
        {"id": 3, "name": "示例3", "value": 300}
    ]
