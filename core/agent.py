import json
from openai import AsyncOpenAI, APIStatusError, APIConnectionError
from langchain_core.utils.function_calling import convert_to_openai_tool

class ScamAgent:
    def __init__(self, user_data, mcp_client=None, debug_mode=False):
        self.id = user_data["id"]
        self.name = user_data["name"]
        self.system_prompt = user_data["system_prompt"]
        self.debug_mode = debug_mode
        
        self.model_name = user_data.get("model", "gpt-4o")
        
        # 模拟浏览器指纹，防止部分 API 服务商拦截
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        self.client = AsyncOpenAI(
            api_key=user_data.get("api_key"),
            base_url=user_data.get("base_url"),
            max_retries=2, 
            timeout=30.0,
            default_headers=browser_headers
        )
        
        self.mcp_client = mcp_client
        self.tools_map = {}     
        self.openai_tools = [] 

    async def init_tools(self):
        """初始化工具并转换为 OpenAI 格式 (增强版)"""
        if self.mcp_client:
            try:
                # 尝试从 MCP Client 加载 LangChain 格式工具
                lc_tools = await self.mcp_client.get_tools()
                
                if self.debug_mode:
                    print(f"[DEBUG] {self.name}: 正在从 MCP 加载工具... 发现 {len(lc_tools)} 个")
                
                self.tools_map = {t.name: t for t in lc_tools}
                self.openai_tools = []
                
                for t in lc_tools:
                    try:
                        # 转换工具定义
                        tool_def = convert_to_openai_tool(t)
                        
                        # 兼容性检查：确保 type 字段存在
                        if "type" not in tool_def:
                            tool_def = {"type": "function", "function": tool_def}
                            
                        self.openai_tools.append(tool_def)
                        
                        if self.debug_mode:
                            print(f"[DEBUG]   -> 已挂载工具: {t.name}")
                            
                    except Exception as e:
                        print(f"[WARN] {self.name}: 转换工具 {t.name} 失败: {e}")

            except Exception as e:
                print(f"[ERROR] {self.name}: MCP 工具加载失败 (连接错误或 Server 未启动): {e}")

    def _build_context(self, global_history):
        """构建 OpenAI 格式消息列表"""
        messages = [{"role": "system", "content": self.system_prompt}]
        user_buffer = []

        for msg in global_history:
            if msg['role_id'] == self.id:
                if user_buffer:
                    content_json = json.dumps(user_buffer, ensure_ascii=False)
                    messages.append({"role": "user", "content": content_json})
                    user_buffer = [] 
                messages.append({"role": "assistant", "content": msg['content']})
            else:
                user_buffer.append({msg['role_name']: msg['content']})

        if user_buffer:
            content_json = json.dumps(user_buffer, ensure_ascii=False)
            messages.append({"role": "user", "content": content_json})
            
        return messages

    async def generate_response(self, global_history) -> str:
        """执行 ReAct 循环"""
        current_messages = self._build_context(global_history)

        if self.debug_mode:
            print(f"\n[DEBUG] {self.name} 正在请求模型: {self.model_name}")
        
        while True:
            try:
                request_kwargs = {
                    "model": self.model_name,
                    "messages": current_messages,
                }
                
                # 关键修改：明确挂载工具
                if self.openai_tools:
                    request_kwargs["tools"] = self.openai_tools
                    request_kwargs["tool_choice"] = "auto"
                    if self.debug_mode:
                        print(f"[DEBUG] Request 包含 {len(self.openai_tools)} 个工具定义")
                else:
                    if self.debug_mode and self.mcp_client:
                        print(f"[DEBUG] 警告: MCP Client 存在但工具列表为空，本次请求无 Function Call 能力")

                # 打印 Payload (仅 Debug)
                if self.debug_mode:
                    print("-" * 20 + " Payload Preview " + "-" * 20)
                    debug_kwargs = request_kwargs.copy()
                    
                    # OpenAI 的 ChatCompletionMessage 对象无法直接序列化
                    safe_messages = []
                    for m in current_messages:
                        if hasattr(m, "model_dump"): # OpenAI V1+ 对象
                            safe_messages.append(m.model_dump())
                        elif hasattr(m, "dict"): # 旧版本兼容
                            safe_messages.append(m.dict())
                        else:
                            safe_messages.append(m) # 普通 dict

                    debug_kwargs['messages'] = safe_messages
                    
                    try:
                        print(json.dumps(debug_kwargs, ensure_ascii=False, indent=2))
                    except TypeError:
                        print("[DEBUG] 无法序列化 Payload，跳过打印")
                    print("-" * 57)

                # 发起请求
                response = await self.client.chat.completions.create(**request_kwargs)
                response_msg = response.choices[0].message
                current_messages.append(response_msg)

                # 处理工具调用
                if response_msg.tool_calls:
                    if self.debug_mode:
                        print(f"[DEBUG] >>> 模型触发工具调用: {len(response_msg.tool_calls)} 个")
                    
                    for tool_call in response_msg.tool_calls:
                        func_name = tool_call.function.name
                        func_args_str = tool_call.function.arguments
                        call_id = tool_call.id
                        
                        if self.debug_mode:
                            print(f"[DEBUG] 执行: {func_name} | 参数: {func_args_str}")
                        
                        content_result = ""
                        if func_name in self.tools_map:
                            try:
                                args = json.loads(func_args_str)
                                # 使用 LangChain 工具的 ainvoke
                                observation = await self.tools_map[func_name].ainvoke(args)
                                content_result = str(observation)
                            except Exception as e:
                                content_result = f"Error: {str(e)}"
                        else:
                            content_result = f"Error: Tool {func_name} not found."

                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": func_name,
                            "content": content_result
                        })
                    continue # 继续循环，将结果发回模型
                
                else:
                    content = response_msg.content
                    if self.debug_mode:
                        print(f"[DEBUG] 模型最终回复: {content}")
                    return content if content else ""

            except APIStatusError as e:
                print(f"\n[API Error] Status: {e.status_code}")
                if self.debug_mode and e.body:
                    print(json.dumps(e.body, ensure_ascii=False))
                raise e
            except APIConnectionError as e:
                print(f"\n[Connection Error] {e}")
                raise e
            except Exception as e:
                print(f"\n[Runtime Error] {e}")
                raise e