from langchain_mcp_adapters.client import MultiServerMCPClient

class MCPClientManager:
    def __init__(self, mcp_registry):
        """
        mcp_registry: 来自 config.json 的 mcp_registry 部分
        """
        self.registry = mcp_registry

    def get_client_for_agent(self, agent_mcp_servers):
        """
        根据角色需要的 server 列表，创建一个私有的 MCP 客户端
        """
        # 过滤出该角色需要的服务器配置
        agent_configs = {
            name: self.registry[name] 
            for name in agent_mcp_servers 
            if name in self.registry
        }
        
        if not agent_configs:
            return None
            
        return MultiServerMCPClient(agent_configs)