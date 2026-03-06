# AI小说工具 API 配置说明

本文档说明当前版本 `api_keys.json` 的实际配置结构，以及应用内相关页面的行为。

![API配置界面](image/1.png)

## 配置文件位置

- 默认文件名：`api_keys.json`
- 应用会优先在项目根目录或程序所在目录查找
- 打包产物默认不附带该文件
- 如果 `API测试` 页点击 `新增配置` 时目标位置还没有配置文件，程序会自动创建

## 当前配置格式

```json
{
  "gemini_api": [
    {
      "name": "Gemini 主配置",
      "key": "你的Gemini API密钥",
      "model": "gemini-2.0-flash",
      "redirect_url": "https://generativelanguage.googleapis.com/v1beta/models",
      "concurrency": 1
    }
  ],
  "openai_api": [
    {
      "name": "DeepSeek 主配置",
      "key": "你的OpenAI或兼容接口密钥",
      "model": "deepseek-chat",
      "redirect_url": "https://api.deepseek.com/v1/chat/completions",
      "concurrency": 2
    }
  ]
}
```

## 配置项说明

- `name`
  - 可选
  - 用于在界面中区分不同配置
  - `提示词调整`、`API测试`、`配置状态` 等界面会优先显示这个名字

- `key`
  - 必填
  - API 密钥或兼容接口所需的认证串

- `model`
  - 可选
  - 模型名称
  - 留空时会回退到对应服务的默认模型

- `redirect_url`
  - 可选
  - 自定义接口地址
  - 留空时使用官方默认地址

- `concurrency`
  - 必填，建议 `1` 起步
  - 表示这条配置允许同时处理的任务数
  - 总可用并发数 = 当前所有可用配置的 `concurrency` 之和

## 已废弃字段

当前版本已经不再使用以下字段：

- `rpm`
- `max_rpm`
- `preferred_api`

如果旧配置文件中仍包含这些字段，程序在加载/保存时会自动忽略或移除。

## Gemini 配置示例

```json
{
  "gemini_api": [
    {
      "name": "Gemini-A",
      "key": "你的第一个Gemini密钥",
      "model": "gemini-2.0-flash",
      "redirect_url": "https://generativelanguage.googleapis.com/v1beta/models",
      "concurrency": 1
    },
    {
      "name": "Gemini-B",
      "key": "你的第二个Gemini密钥",
      "model": "gemini-2.0-flash",
      "concurrency": 2
    }
  ]
}
```

## OpenAI / 兼容接口示例

```json
{
  "openai_api": [
    {
      "name": "OpenAI 官方",
      "key": "你的OpenAI密钥",
      "model": "gpt-4o-mini",
      "redirect_url": "https://api.openai.com/v1/chat/completions",
      "concurrency": 1
    },
    {
      "name": "DeepSeek",
      "key": "你的DeepSeek密钥",
      "model": "deepseek-chat",
      "redirect_url": "https://api.deepseek.com/v1/chat/completions",
      "concurrency": 2
    }
  ]
}
```

## 本地模型示例

### LM Studio

```json
{
  "openai_api": [
    {
      "name": "LM Studio",
      "key": "local",
      "model": "你部署的模型名称",
      "redirect_url": "http://localhost:1234/v1/chat/completions",
      "concurrency": 1
    }
  ]
}
```

### Ollama 兼容端点

```json
{
  "openai_api": [
    {
      "name": "Ollama",
      "key": "ollama",
      "model": "llama3",
      "redirect_url": "http://localhost:11434/v1/chat/completions",
      "concurrency": 1
    }
  ]
}
```

## 当前调度逻辑

### 1. 混合模式

- 如果同时存在 Gemini 和 OpenAI 配置，脱水任务会在两类服务之间分流
- 如果只有一类服务可用，则只使用该类服务

### 2. 同类配置内部调度

- 同类配置会由运行时调度器自动分配
- 调度时会综合考虑：
  - 当前实际占用并发数
  - 配置的并发上限
  - 最近成功率
  - 轮换顺序

### 3. 失败冷却与废弃

单条配置实例的处理策略如下：

- 连续失败 `3` 次：进入冷却
- 连续失败 `4` 次：冷却时间继续增长
- 连续失败 `5` 次及以上：进入 `10` 分钟冷却
- 累计失败 `20` 次：本轮任务中跳过该配置
- 所有配置都不可用时：进入全局冷却

## 应用内相关页面

### API测试

- 支持 `新增配置 / 编辑 / 删除 / 测试`
- 新增或修改配置时会直接写回 `api_keys.json`
- 测试采用快速超时策略，不再长时间卡住

### 脱水处理

- `配置状态` 按钮可查看当前任务周期内每个配置的：
  - 本次任务状态
  - 实际并发数
  - 配置并发数
  - 成功请求数
  - 失败请求数
  - 成功率

### 提示词调整

- `选择API密钥` 下拉框优先显示配置里的 `name`

## 建议

- 初始建议每条配置从 `concurrency: 1` 开始
- 如果某个服务稳定、响应快，再逐步提高到 `2` 或 `3`
- 本地模型和第三方代理通常更容易出现慢响应，建议保守设置并发
- 配置较多时，优先为每条配置填写 `name`，便于在界面中排查问题
