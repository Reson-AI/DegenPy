# DegenPy 插件系统

这个目录包含 DegenPy 的插件系统，允许开发者扩展 DegenPy 的功能而不需要修改核心代码。

## 插件结构

每个插件应该是一个独立的 Python 包，放置在 `plugins` 目录下。插件的基本结构如下：

```
plugins/
  ├── example/              # 插件包目录
  │   ├── __init__.py       # 插件初始化文件
  │   ├── core.py           # 插件核心功能
  │   └── ...               # 其他插件模块
  └── ...                   # 其他插件
```

## 创建新插件

要创建一个新插件，请按照以下步骤操作：

1. 在 `plugins` 目录下创建一个新的目录，使用你的插件名称
2. 创建 `__init__.py` 文件，包含以下内容：
   - 插件的元数据（名称、版本、描述等）
   - `setup()` 函数，用于插件初始化
   - 导出插件的公共 API
3. 实现插件的核心功能

## 插件示例

`example` 插件展示了如何创建一个基本的插件。你可以查看它的代码作为参考。

## 使用插件

以下是使用插件的基本示例：

```python
# 导入插件系统
from plugins import load_plugin, load_all_plugins

# 加载特定插件
example_plugin = load_plugin('example')
if example_plugin:
    # 使用插件功能
    tool = example_plugin.ExampleTool()
    result = tool.process_data("测试数据")
    print(result)

# 或者加载所有可用的插件
all_plugins = load_all_plugins()
for name, plugin in all_plugins.items():
    print(f"已加载插件: {name}")
```

## 插件开发指南

开发插件时，请遵循以下最佳实践：

1. 每个插件应该有一个明确的功能范围
2. 插件应该提供良好的文档和类型注解
3. 插件应该处理自己的异常，不应该让异常传播到主应用程序
4. 插件应该提供一个 `setup()` 函数进行初始化
5. 插件应该定义 `NAME`, `VERSION` 和 `DESCRIPTION` 常量
