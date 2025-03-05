#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
插件系统测试脚本

这个脚本演示了如何使用 DegenPy 的插件系统。
"""

from plugins import discover_plugins, load_plugin, load_all_plugins

def test_discover_plugins():
    """测试发现可用插件"""
    print("\n=== 测试发现可用插件 ===")
    plugins = discover_plugins()
    print(f"发现 {len(plugins)} 个插件:")
    for plugin in plugins:
        print(f"  - {plugin}")
    return plugins

def test_load_specific_plugin(plugin_name):
    """测试加载特定插件"""
    print(f"\n=== 测试加载插件: {plugin_name} ===")
    plugin = load_plugin(plugin_name)
    
    if plugin:
        print(f"插件信息:")
        print(f"  - 名称: {getattr(plugin, 'NAME', '未知')}")
        print(f"  - 版本: {getattr(plugin, 'VERSION', '未知')}")
        print(f"  - 描述: {getattr(plugin, 'DESCRIPTION', '未知')}")
        
        # 测试插件功能
        if hasattr(plugin, 'ExampleTool'):
            tool = plugin.ExampleTool()
            result = tool.process_data("测试数据")
            print("\n工具处理结果:")
            for key, value in result.items():
                print(f"  - {key}: {value}")
            
            info = tool.get_info()
            print("\n工具信息:")
            for key, value in info.items():
                print(f"  - {key}: {value}")
        
        if hasattr(plugin, 'get_example_data'):
            data = plugin.get_example_data()
            print("\n示例数据:")
            for item in data:
                print(f"  - {item}")
    else:
        print(f"无法加载插件: {plugin_name}")

def test_load_all_plugins():
    """测试加载所有插件"""
    print("\n=== 测试加载所有插件 ===")
    plugins = load_all_plugins()
    print(f"成功加载 {len(plugins)} 个插件:")
    for name, plugin in plugins.items():
        print(f"  - {name} v{getattr(plugin, 'VERSION', '未知')}")

def main():
    """主测试函数"""
    print("=== DegenPy 插件系统测试 ===")
    
    # 测试发现插件
    available_plugins = test_discover_plugins()
    
    # 测试加载特定插件
    if 'example' in available_plugins:
        test_load_specific_plugin('example')
    
    # 测试加载所有插件
    test_load_all_plugins()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()
