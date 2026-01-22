# MASS: Multi-Agent Scam Interaction Framework

MASS (Multi-Agent Scam Simulator) 是一个专为测试多智能体在诈骗与反诈场景下交互表现设计的 Python 命令行框架。本项目通过严格的上下文隔离机制，确保多个角色（如诈骗者、受害者、中间人、银行客服等）能够维持各自的人设，并利用 Model Context Protocol (MCP) 实现私有的工具调用能力。

## 1. 核心设计理念

* **人设持久化**：每个角色拥有独立的 System Prompt，强制维持角色扮演，确保在多轮对话中不出戏。
* **隐私工具链**：集成 LangChain MCP 库。每个角色的工具配置是独立的，其工具调用过程（Tool Call）和返回的原始数据（Tool Output）仅对该角色可见，其他角色只能看到该角色最终发出的文本回复。
* **统一接口**：底层统一支持 OpenAI API 格式（Chat Completions），兼容所有支持该协议的服务商（OpenAI, DeepSeek, Local LLMs 等）。
* **非对称信息模拟**：通过 `user.json` 配置差异化工具，模拟诈骗中常见的信息差环境。

## 2. 目录结构

```text
.
├── main.py                 # CLI 交互与程序入口
├── core/
│   ├── agent.py            # 基于 LangChain 的 OpenAI 模型包装与 MCP 逻辑
│   ├── manager.py          # 负责对话流转与角色调度
│   └── mcp_client.py       # MCP 客户端生命周期管理
├── config.json             # 全局环境配置
├── user.json               # 角色定义与私有工具配置
├── history/                # 对话导出与加载目录
└── servers/                # 自定义 MCP 服务器脚本存放处
```

## 3. 配置文件规范

### 3.1 user.json

定义 7 个或更多角色。每个角色是一个独立实体。

```json
[
  {
    "id": "agent_01",
    "name": "王大强",
    "system_prompt": "你是一个65岁的退休老人，对数字支付不熟悉，容易相信他人...",
    "api_key": "sk-xxx",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "mcp_servers": ["bank_service"],
  },
  {
    "id": "agent_02",
    "name": "李经理",
    "system_prompt": "你是一名假冒的银行安全专家，话术极具诱导性...",
    "api_key": "sk-yyy",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "mcp_servers": ["scam_scripts"],
  }
]
```

### 3.2 config.json

定义项目运行参数及 MCP 服务映射。

```json
{
  "max_rounds": -1, 
  "save_on_exit": true,
  "mcp_registry": {
    "bank_service": {
      "command": "python",
      "args": ["servers/bank_mcp.py"],
      "transport": "stdio"
    },
    "scam_scripts": {
      "command": "node",
      "args": ["servers/script_mcp.js"],
      "transport": "stdio"
    }
  }
}
```

## 4. 关键功能实现设计

### 4.1 MCP 工具隔离

使用 `langchain-mcp-adapters` 为每个角色实例化私有的 `MultiServerMCPClient`。

* **执行流程**：角色 A 接收对话历史 -> 触发工具调用 -> 在 A 的私有环境中执行 -> A 得到结果 -> A 生成文本回复。
* **不可见性**：其他角色的对话历史中只会追加 A 的文本回复，`ToolRequest` 和 `ToolResponse` 消息会被过滤掉，从而保证工具调用的隐蔽性。

### 4.2 导出与恢复逻辑

对话记录保存为 `history_XXXX.json`。

* **保存内容**：包含 `role_id`、`role_name`、`content` 和时间戳。
* **恢复机制**：读取 JSON 后，程序将按顺序重新填充每个 Agent 的 `ChatMessageHistory`。由于 System Prompt 依然从 `user.json` 读取，Agent 将基于历史语境继续角色扮演。

## 5. CLI 交互指令

启动项目后，用户通过命令行控制对话节奏：

| 指令       | 参数       | 说明                                               |
| :--------- | :--------- | :------------------------------------------------- |
| `speak`  | `<id>`   | 强制指定 ID 为 `<id>` 的角色生成下一条回复       |
| `auto`   | `<n>`    | 按照 `user.json` 中的顺序自动循环对话 `<n>` 轮 |
| `show`   | -          | 打印当前所有角色的可见对话历史                     |
| `export` | `[name]` | 将当前对话状态保存至 `./history/[name].json`     |
| `load`   | `<path>` | 从指定文件导入对话记录并初始化所有角色状态         |
| `status` | -          | 查看当前已加载的角色及其关联的私有工具             |
| `exit`   | -          | 退出并根据配置自动保存                             |

## 6. 代码参考 (LangChain MCP Adapter)

在 `core/agent.py` 中，针对 OpenAI 格式模型的 MCP 集成参考：

```python
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_react_agent, AgentExecutor

async def setup_agent(user_data, mcp_registry):
    # 初始化 OpenAI 模型
    llm = ChatOpenAI(
        api_key=user_data["api_key"],
        base_url=user_data["base_url"],
        model=user_data["model"]
    )
  
    # 初始化该角色的私有 MCP 客户端
    mcp_configs = {k: v for k, v in mcp_registry.items() if k in user_data["mcp_servers"]}
    mcp_client = MultiServerMCPClient(mcp_configs)
    private_tools = await mcp_client.get_tools()
  
    # 封装为 AgentExecutor，仅将文本回复返回给全局管理器
    # 内部工具逻辑对外部透明
    agent = create_private_executor(llm, private_tools, user_data["system_prompt"])
    return agent
```

## 7. 注意事项

1. **角色一致性**：若角色出现出戏现象，需在 `user.json` 的 `system_prompt` 中增加 `Please strictly adhere to your persona and do not mention you are an AI.`。
2. **MCP 服务器**：确保在运行前，`config.json` 中定义的命令（如 `python` 或 `node`）在系统路径中可用。
3. **API 消耗**：多角色自动对话会快速消耗 Token，建议在 `config.json` 中设置合理的 `max_rounds`。
