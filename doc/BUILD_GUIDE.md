# AI小说工具打包指南

本文档描述当前仓库实际可用的打包方式。入口脚本是 `run.py`，根目录已包含可直接使用的 `AINovelLab.spec`。

## 环境要求

- Python `3.8+`
- 已安装 `requirements.txt` 中的依赖
- 建议使用 Windows PowerShell

## 方式一：直接使用 spec 打包

1. 安装依赖：

```powershell
pip install -r "requirements.txt"
```

2. 执行打包：

```powershell
pyinstaller "AINovelLab.spec"
```

3. 产物位置：

- 程序目录：`dist/AINovelLab`
- 可执行文件：`dist/AINovelLab/AINovelLab.exe`

## 方式二：使用封装脚本

统一打包入口是 `scripts/build.py`：

```powershell
python "scripts/build.py"
```

该脚本会：

- 检查 `PyInstaller` 是否已安装
- 清理旧的 `build/`、`dist/` 和同名 `.spec`
- 调用 `PyInstaller` 打包

兼容入口：

- `python "scripts/build_exe.py"`
- `python "scripts/quick_build.py"`

## 当前 spec 包含内容

`AINovelLab.spec` 会把以下内容带入发布目录：

- `resources/`
- `data/`
- `config/`
- `src/`

显式包含的关键依赖：

- `PyQt5`
- `ebooklib`
- `beautifulsoup4`
- `requests`
- `lxml`
- `tqdm`

## 分发建议

建议分发整个目录，而不是只分发单个 exe：

```powershell
Compress-Archive -Path "dist/AINovelLab" -DestinationPath "dist/AINovelLab.zip"
```

原因：

- Qt 运行时和资源文件需要随程序一起发布
- 主题样式来自 `resources/material_dark.qss`

## 打包后的配置文件

打包产物默认不再附带 `api_keys.json`。

如果用户首次打开后还没有配置文件，可以在 `API测试` 页面点击 `新增配置`，程序会自动创建配置文件并写入首条配置。

当前模板结构使用每条配置独立的 `concurrency` 字段控制并发，例如：

```json
{
  "gemini_api": [
    {
      "name": "Gemini 主配置",
      "key": "你的Gemini API密钥",
      "model": "gemini-2.0-flash",
      "concurrency": 1
    }
  ],
  "openai_api": [
    {
      "name": "DeepSeek 主配置",
      "key": "你的兼容 OpenAI API 密钥",
      "model": "deepseek-chat",
      "concurrency": 1
    }
  ]
}
```

已废弃字段：

- `rpm`
- `max_rpm`

## 常见问题

### 1. `pyinstaller AINovelLab.spec` 失败

先确认依赖已安装：

```powershell
pip install -r "requirements.txt"
```

如果仍失败，优先检查：

- 当前目录是否为项目根目录
- 当前 Python 环境是否与安装依赖时一致

### 2. 打包后程序启动即退出

优先排查：

- `dist/AINovelLab` 下是否包含 `resources/`、`src/`、`config/`
- 配置是否仍保留旧字段而缺少 `concurrency`

### 3. 想显示控制台窗口方便调试

可以使用：

```powershell
python "scripts/build.py" --console
```

### 4. 想修改输出程序名

可以使用：

```powershell
python "scripts/build.py" --name "MyNovelTool"
```
