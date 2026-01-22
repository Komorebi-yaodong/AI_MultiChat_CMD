import json
import os
from datetime import datetime
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
        self.global_history = [] 

    async def initialize_agents(self):
        """初始化所有角色及其私有工具链"""
        debug_mode = self.config.get("debug_mode", False)
        
        for user_data in self.users_data:
            mcp_client = self.mcp_manager.get_client_for_agent(user_data.get("mcp_servers", []))
            agent = ScamAgent(user_data, mcp_client, debug_mode=debug_mode)
            await agent.init_tools()
            self.agents[user_data["id"]] = agent
    
    def set_debug(self, enabled: bool):
        self.config["debug_mode"] = enabled
        for agent in self.agents.values():
            agent.debug_mode = enabled
        print(f"Debug 模式已{'开启' if enabled else '关闭'}。")

    async def agent_speak(self, agent_id: str):
        """让指定角色生成下一条消息"""
        if agent_id not in self.agents:
            return None

        agent = self.agents[agent_id]
        
        # 获取回复文本 和 内部思考过程(工具调用日志)
        response_text, internal_thoughts = await agent.generate_response(self.global_history)
        
        message_entry = {
            "role_id": agent.id,
            "role_name": agent.name,
            "content": response_text,
            "timestamp": datetime.now().isoformat(),
            # 这里保存了工具调用链，用于该角色后续的上下文恢复，以及导出
            "internal_thoughts": internal_thoughts 
        }
        self.global_history.append(message_entry)
        
        return message_entry

    def delete_message(self, index: int):
        """根据序号删除消息"""
        # 由于 internal_thoughts 现在封装在 message_entry 中
        # 删除这个 entry 会自动连带删除所有的 tool calls
        if 0 <= index < len(self.global_history):
            removed = self.global_history.pop(index)
            return removed
        return None

    def export_history(self, filename=None):
        """将历史记录导出为 JSON，包含工具调用详情"""
        if not filename:
            filename = f"history_{datetime.now().strftime('%m%d_%H%M')}.json"
        
        path = os.path.join("history", filename)
        os.makedirs("history", exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            # internal_thoughts 已经是 dict 格式，可以直接序列化
            json.dump(self.global_history, f, ensure_ascii=False, indent=2)
        return path

    async def load_history(self, file_path):
        """从文件加载历史记录"""
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return
            
        with open(file_path, 'r', encoding='utf-8') as f:
            self.global_history = json.load(f)