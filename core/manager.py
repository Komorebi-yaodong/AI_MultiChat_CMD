import json
import os
from datetime import datetime
# 注意：新逻辑下 manager 不再直接操作 langchain 消息对象，因此移除了 message 相关导入
from .agent import ScamAgent
from .mcp_client import MCPClientManager

class DialogueManager:
    def __init__(self, config_path="config.json", user_path="user.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        with open(user_path, 'r', encoding='utf-8') as f:
            self.users_data = json.load(f)

        self.mcp_manager = MCPClientManager(self.config.get("mcp_registry", {}))
        self.agents = {}
        self.global_history = []  # 存放全局对话记录列表（纯文本字典格式）

    async def initialize_agents(self):
        """初始化所有角色及其私有工具链"""
        # 读取配置中的 debug 设定
        debug_mode = self.config.get("debug_mode", False)
        
        for user_data in self.users_data:
            mcp_client = self.mcp_manager.get_client_for_agent(user_data.get("mcp_servers", []))
            # Agent 初始化，传入 debug_mode
            agent = ScamAgent(user_data, mcp_client, debug_mode=debug_mode)
            await agent.init_tools()
            self.agents[user_data["id"]] = agent
    
    def set_debug(self, enabled: bool):
        """[新增] 运行时切换 Debug 模式"""
        self.config["debug_mode"] = enabled
        for agent in self.agents.values():
            agent.debug_mode = enabled
        print(f"Debug 模式已{'开启' if enabled else '关闭'}。")

    async def agent_speak(self, agent_id: str):
        """让指定角色生成下一条消息"""
        if agent_id not in self.agents:
            return None

        agent = self.agents[agent_id]
        
        # [修改] 传入完整的 global_history，由 Agent 内部根据自己的视角构建 Context
        # 这样可以解决 "User/Assistant" 顺序错乱导致的 API 400/Block 问题
        response_text = await agent.generate_response(self.global_history)
        
        message_entry = {
            "role_id": agent.id,
            "role_name": agent.name,
            "content": response_text,
            "timestamp": datetime.now().isoformat()
        }
        self.global_history.append(message_entry)
        
        return message_entry

    def delete_message(self, index: int):
        """根据序号删除消息"""
        if 0 <= index < len(self.global_history):
            removed = self.global_history.pop(index)
            # 无需 resync，因为现在 Agent 是 Stateless 的，
            # 下次调用 agent_speak 时会动态读取被删减后的 global_history
            return removed
        return None

    def export_history(self, filename=None):
        """将脱敏后的历史记录导出为 JSON"""
        if not filename:
            filename = f"history_{datetime.now().strftime('%m%d_%H%M')}.json"
        
        path = os.path.join("history", filename)
        os.makedirs("history", exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.global_history, f, ensure_ascii=False, indent=2)
        return path

    async def load_history(self, file_path):
        """从文件加载历史记录"""
        if not os.path.exists(file_path):
            return
            
        with open(file_path, 'r', encoding='utf-8') as f:
            self.global_history = json.load(f)
        # 加载后无需操作，状态在 global_history 中