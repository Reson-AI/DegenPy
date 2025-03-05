#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
示例插件

这是一个示例插件，展示了如何创建 DegenPy 插件。
"""

from .core import ExampleTool, get_example_data

__all__ = ['ExampleTool', 'get_example_data', 'setup', 'NAME', 'VERSION', 'DESCRIPTION']

NAME = "example"
VERSION = "0.1.0"
DESCRIPTION = "示例插件，用于展示插件系统的功能"

def setup():
    """
    插件初始化函数
    
    当插件被加载时，此函数会被调用
    """
    print(f"插件 '{NAME}' v{VERSION} 已加载")
    return True
