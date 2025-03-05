#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DegenPy 插件系统

这个模块提供了扩展 DegenPy 功能的插件架构。
插件可以添加新的功能，而不需要修改核心代码。
"""

import os
import importlib
import pkgutil
from typing import Dict, List, Any, Callable, Optional

# 存储已加载的插件
_loaded_plugins = {}

def discover_plugins() -> List[str]:
    """
    发现可用的插件模块
    
    返回:
        插件名称列表
    """
    plugins_dir = os.path.dirname(__file__)
    return [name for _, name, is_pkg in pkgutil.iter_modules([plugins_dir])
            if not name.startswith('_') and is_pkg]

def load_plugin(plugin_name: str) -> Optional[Any]:
    """
    加载指定的插件
    
    参数:
        plugin_name: 插件名称
        
    返回:
        插件模块对象，如果加载失败则返回 None
    """
    if plugin_name in _loaded_plugins:
        return _loaded_plugins[plugin_name]
        
    try:
        plugin_module = importlib.import_module(f"plugins.{plugin_name}")
        if hasattr(plugin_module, 'setup'):
            plugin_module.setup()
        _loaded_plugins[plugin_name] = plugin_module
        return plugin_module
    except Exception as e:
        print(f"Error loading plugin '{plugin_name}': {str(e)}")
        return None

def load_all_plugins() -> Dict[str, Any]:
    """
    加载所有可用的插件
    
    返回:
        插件名称到插件模块对象的映射
    """
    plugins = {}
    for plugin_name in discover_plugins():
        plugin = load_plugin(plugin_name)
        if plugin:
            plugins[plugin_name] = plugin
    return plugins

def get_plugin(plugin_name: str) -> Optional[Any]:
    """
    获取已加载的插件
    
    参数:
        plugin_name: 插件名称
        
    返回:
        插件模块对象，如果插件未加载则返回 None
    """
    if plugin_name not in _loaded_plugins:
        return load_plugin(plugin_name)
    return _loaded_plugins[plugin_name]
