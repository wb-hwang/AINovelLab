# AI小说工具项目结构说明

本文档基于当前仓库实际目录整理，重点说明核心模块职责和构建文件。

## 顶层目录

```text
AINovelLab/
├── config/                 # 运行配置与兼容层
├── data/                   # 示例或运行期数据目录
├── doc/                    # 项目文档
├── resources/              # QSS 主题与静态资源
├── scripts/                # 打包与回归脚本
├── src/                    # 应用源代码
├── api_keys.json           # API 配置文件
├── AINovelLab.spec         # PyInstaller 打包配置
├── requirements.txt        # Python 依赖
├── run.py                  # 桌面应用入口脚本
└── README.md               # 项目总说明
```

## `src/` 结构

```text
src/
├── main.py
├── version.py
├── core/
│   ├── epub_splitter.py
│   ├── txt_to_epub.py
│   ├── utils.py
│   └── novel_condenser/
│       ├── api_service.py
│       ├── config.py
│       ├── file_utils.py
│       ├── key_manager.py
│       ├── main.py
│       └── stats.py
└── gui/
    ├── api_test_tab.py
    ├── condenser_tab.py
    ├── epub_splitter_tab.py
    ├── home_tab.py
    ├── main_window.py
    ├── prompt_edit_dialog.py
    ├── resources.py
    ├── style.py
    ├── txt_to_epub_tab.py
    ├── ui_components.py
    └── worker.py
```

## 核心模块职责

### `src/core/`

- `epub_splitter.py`
  - 负责 EPUB 解析和章节拆分
  - 输出命名规范化的 TXT 文件

- `txt_to_epub.py`
  - 按文件顺序合并 TXT
  - 生成目录完整的 EPUB 文件

- `novel_condenser/main.py`
  - 组织脱水任务主流程
  - 连接文件处理、配置加载、调度器与统计模块

- `novel_condenser/api_service.py`
  - 封装 Gemini / OpenAI 兼容接口调用
  - 提供正式任务请求与 API 测试请求

- `novel_condenser/key_manager.py`
  - 管理每条配置的并发额度
  - 维护失败冷却、跳过策略和运行状态统计

- `novel_condenser/config.py`
  - 读写 `api_keys.json`
  - 规范化配置项，移除已废弃字段

### `src/gui/`

- `main_window.py`
  - 主窗口与标签页装配

- `home_tab.py`
  - 首页仪表盘和功能说明

- `epub_splitter_tab.py`
  - EPUB 转 TXT 工作台

- `condenser_tab.py`
  - 脱水处理工作台
  - 包含 `配置状态` 弹窗入口

- `txt_to_epub_tab.py`
  - TXT 转 EPUB 工作台

- `api_test_tab.py`
  - API 配置管理与测试页面
  - 支持新增、编辑、删除、测试配置

- `prompt_edit_dialog.py`
  - 提示词模板编辑与单次脱水测试对话框

- `ui_components.py`
  - 通用卡片、状态标签、弹窗辅助组件

- `worker.py`
  - 后台线程任务封装，避免 UI 阻塞

## `config/` 目录

- `config.py`
  - 桌面应用侧配置加载入口
  - 同步当前 `concurrency` 模型

- `config_compat.py`
  - 兼容旧配置和运行环境差异

## `scripts/` 目录

- `build.py`
  - 统一的 PyInstaller 打包入口

- `build_exe.py`
  - 兼容旧用法的打包包装脚本

- `quick_build.py`
  - 快速打包包装脚本

- `smoke.py`
  - 最小回归脚本
  - 当前覆盖配置路径和 `TXT -> EPUB` 基本流程

## 配置与资源

- `api_keys.json`
  - 当前使用 `gemini_api` / `openai_api` 双列表结构
  - 每条配置使用 `concurrency` 控制并发

- `resources/material_dark.qss`
  - 全局暗色主题样式表

## 入口与构建

- `run.py`
  - 添加项目根目录到 `sys.path`
  - 启动 `src.main.main()`

- `AINovelLab.spec`
  - 当前可直接用于 `pyinstaller AINovelLab.spec`

## 关系概览

```text
run.py
  └─ src/main.py
      └─ gui/main_window.py
          ├─ home_tab.py
          ├─ epub_splitter_tab.py
          ├─ condenser_tab.py
          │   └─ worker.py -> core/novel_condenser/*
          ├─ txt_to_epub_tab.py
          └─ api_test_tab.py -> core/novel_condenser/config.py
```
