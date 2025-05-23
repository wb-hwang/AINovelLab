# AI小说工具项目结构说明

本文档详细介绍了AI小说工具的项目结构和各模块功能。

![项目结构概览](image/1.png)

## 目录结构

```
AINovelLab/
├── src/                   # 源代码目录
│   ├── core/              # 核心功能模块
│   │   ├── epub_splitter.py    # EPUB分割器
│   │   ├── novel_condenser/    # 小说脱水工具(模块化)
│   │   │   ├── __init__.py       # 包初始化文件
│   │   │   ├── main.py           # 主模块
│   │   │   ├── api_service.py    # API服务
│   │   │   ├── file_utils.py     # 文件处理
│   │   │   ├── config.py         # 配置管理
│   │   │   ├── key_manager.py    # 密钥管理
│   │   │   └── stats.py          # 统计模块
│   │   ├── txt_to_epub.py      # TXT合并转EPUB工具
│   │   ├── api_manager.py      # API密钥管理
│   │   └── utils.py            # 通用工具函数
│   ├── gui/               # GUI相关代码
│   │   ├── main_window.py    # 主窗口
│   │   ├── home_tab.py       # 首页标签
│   │   ├── epub_splitter_tab.py # EPUB分割标签
│   │   ├── condenser_tab.py  # 脱水工具标签
│   │   ├── txt_to_epub_tab.py  # TXT转EPUB标签
│   │   └── worker.py         # 后台工作线程
│   ├── version.py         # 版本信息
│   ├── import_helper.py    # 导入路径设置辅助模块
│   └── main.py            # 主入口
├── config/                # 配置文件目录
│   ├── config.py          # 配置管理模块
│   ├── config_compat.py   # 配置兼容性处理
│   └── default_config.py  # 默认配置
├── api_keys.json          # API密钥配置文件(放在根目录方便打包后修改)
├── data/                  # 数据文件目录
├── resources/             # 资源文件
├── run.py                 # 项目入口脚本
├── AINovelLab.spec       # PyInstaller打包配置文件
└── README.md              # 项目说明文档
```

## 核心模块说明

### EPUB分割器

`src/core/epub_splitter.py` 模块提供以下功能：

- 解析EPUB电子书，提取章节内容
- 按章节分割内容，支持自定义每个文件包含的章节数
- 保存为单独的TXT文件，支持自定义输出格式

### 小说脱水工具

`src/core/novel_condenser/` 目录下的模块集成了小说内容压缩功能：

- `main.py` - 脱水工具的主要逻辑和流程控制
- `api_service.py` - 负责与各种AI API服务通信
- `file_utils.py` - 文件处理工具，包括读写和路径管理
- `config.py` - 配置管理，加载和验证配置
- `key_manager.py` - API密钥管理和轮转
- `stats.py` - 统计模块，追踪处理进度和结果

脱水工具支持多种API服务，可以自动在不同服务间切换，并支持并行处理多个文件。

### TXT合并转EPUB

`src/core/txt_to_epub.py` 模块提供以下功能：

- 读取多个TXT文件，按文件名顺序排序
- 提取文件名中的元数据（书名、章节编号等）
- 生成EPUB格式的电子书，包括目录和章节

## GUI界面

图形界面采用PyQt5开发，分为多个标签页：

- `home_tab.py` - 首页，提供应用使用说明
- `epub_splitter_tab.py` - EPUB分割功能界面
- `condenser_tab.py` - 小说脱水功能界面
- `txt_to_epub_tab.py` - TXT合并为EPUB功能界面
- `worker.py` - 后台工作线程，处理耗时操作，避免界面卡顿

![GUI界面示例](image/2.png)

## 配置管理

配置系统设计为灵活且易于修改：

- 配置文件放在根目录，方便打包后修改
- 使用JSON格式，易于人工编辑
- 配置兼容性处理，支持版本升级时的配置迁移
- 运行时自动重新加载配置，无需重启应用

## 入口脚本

`run.py` 是项目的主要入口点，提供以下功能：

- 设置正确的导入路径
- 检测运行环境（打包环境或开发环境）
- 加载版本信息
- 启动GUI或命令行界面

## 模块间关系

```
                      ┌─────────────┐
                      │    run.py   │
                      └──────┬──────┘
                             │
                             ▼
                      ┌─────────────┐
                      │   main.py   │
                      └──────┬──────┘
                             │
               ┌─────────────┴─────────────┐
               │                           │
               ▼                           ▼
       ┌───────────────┐           ┌───────────────┐
       │     GUI       │           │ Command Line  │
       └───────┬───────┘           └───────┬───────┘
               │                           │
               ▼                           │
       ┌───────────────┐                   │
       │  main_window  │                   │
       └───────┬───────┘                   │
               │                           │
       ┌───────┴───────┐                   │
       ▼               ▼                   ▼
┌─────────────┐  ┌─────────────┐    ┌─────────────┐
│ EPUB Split  │  │  Condenser  │    │ Core Modules│
└──────┬──────┘  └──────┬──────┘    └──────┬──────┘
       │                │                  │
       └────────┬───────┘                  │
                │                          │
                ▼                          ▼
         ┌─────────────┐           ┌─────────────┐
         │API Manager  │◄──────────┤ Config Mgmt │
         └─────────────┘           └─────────────┘
```

## 编码规范

本项目遵循以下编码规范：

1. **PEP 8** - Python代码风格指南
2. **模块化设计** - 每个模块只负责一个功能
3. **统一的导入路径** - 使用导入帮助程序简化导入
4. **异常处理** - 所有可能抛出异常的地方都有适当的处理
5. **日志记录** - 使用Python标准日志模块记录运行状态
6. **类型提示** - 使用类型注解提高代码可读性和可维护性

## 扩展指南

如果你想扩展本项目的功能，以下是推荐的方式：

1. **添加新的API提供商**：修改`api_service.py`和`key_manager.py`模块
2. **添加新的处理算法**：在`novel_condenser`目录下创建新的处理模块
3. **增强GUI功能**：在`gui`目录下修改或添加新的标签页
4. **添加新的输出格式**：扩展`txt_to_epub.py`或创建新的转换模块 