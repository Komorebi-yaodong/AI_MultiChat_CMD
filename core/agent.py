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
        
        # 模拟浏览器指纹
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
        """初始化工具并转换为 OpenAI 格式"""
        if self.mcp_client:
            try:
                lc_tools = await self.mcp_client.get_tools()
                
                if self.debug_mode:
                    print(f"[DEBUG] {self.name}: 正在从 MCP 加载工具... 发现 {len(lc_tools)} 个")
                
                self.tools_map = {t.name: t for t in lc_tools}
                self.openai_tools = []
                
                for t in lc_tools:
                    try:
                        tool_def = convert_to_openai_tool(t)
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
        """构建 OpenAI 格式消息列表，支持私有工具历史回放"""
        messages = [{"role": "system", "content": self.system_prompt}]
        # 使用 buffer 将连续的其他人发言合并为一条 User 消息
        user_buffer = [{"role": "user", "content": f"## system/n/n{self.system_prompt}"}]

        for msg in global_history:
            # 如果是当前 Agent 自己的历史
            if msg['role_id'] == self.id:
                # 1. 先把缓冲区里的“他人发言”结算并加入
                if user_buffer:
                    content_json = json.dumps(user_buffer, ensure_ascii=False)
                    messages.append({"role": "user", "content": content_json})
                    user_buffer = [] 

                # 2. 回放私有的思维链 (internal_thoughts)
                # 这些是工具调用请求(assistant)和工具结果(tool)
                if 'internal_thoughts' in msg and msg['internal_thoughts']:
                    messages.extend(msg['internal_thoughts'])

                # 3. 加入最终对外的回复 (assistant)
                messages.append({"role": "assistant", "content": msg['content']})

            else:
                # 如果是其他人的历史，只看 content，忽略他们的 internal_thoughts
                user_buffer.append({msg['role_name']: msg['content']})

        # 处理最后剩余的 buffer
        if user_buffer:
            content_json = json.dumps(user_buffer, ensure_ascii=False)
            messages.append({"role": "user", "content": content_json})
            
        return messages

    async def generate_response(self, global_history):
        """执行 ReAct 循环，返回 (final_text, tool_logs)"""
        current_messages = self._build_context(global_history)
        
        # 用于记录本轮对话中产生的所有“非最终回复”的消息（即工具调用和工具结果）
        turn_internal_thoughts = []

        if self.debug_mode:
            print(f"\n[DEBUG] {self.name} 正在请求模型: {self.model_name}")
        
        while True:
            try:
                request_kwargs = {
                    "model": self.model_name,
                    "messages": current_messages,
                }
                
                if self.openai_tools:
                    request_kwargs["tools"] = self.openai_tools
                    request_kwargs["tool_choice"] = "auto"
                if self.debug_mode:
                    print("[DEBUG] >>> 正在请求模型: {self.model_name}")
                    print("[DEBUG] >>> 请求参数:")
                    print(request_kwargs)
                # 发起请求
                response = await self.client.chat.completions.create(**request_kwargs)
                response_msg = response.choices[0].message
                
                # 将 OpenAI 对象转为可序列化的 dict，用于历史存储
                response_msg_dict = response_msg.model_dump(exclude_none=True)

                # 处理工具调用
                if response_msg.tool_calls:
                    # 1. 将模型的调用指令加入上下文和本轮日志
                    current_messages.append(response_msg) # 对象用于继续 API 调用
                    turn_internal_thoughts.append(response_msg_dict) # 字典用于存储

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
                                observation = await self.tools_map[func_name].ainvoke(args)
                                content_result = str(observation)
                            except Exception as e:
                                content_result = f"Error: {str(e)}"
                        else:
                            content_result = f"Error: Tool {func_name} not found."

                        # 构建工具返回消息
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": func_name,
                            "content": content_result
                        }
                        
                        # 2. 将工具结果加入上下文和本轮日志
                        current_messages.append(tool_msg)
                        turn_internal_thoughts.append(tool_msg)

                    continue # 拿着工具结果继续循环
                
                else:
                    # 最终回复
                    content = response_msg.content
                    if self.debug_mode:
                        print(f"[DEBUG] 模型最终回复: {content}")
                    
                    # 返回：(最终文本, 中间思考过程)
                    return content if content else "", turn_internal_thoughts

            except APIStatusError as e:
                print(f"\n[API Error] Status: {e.status_code}")
                if self.debug_mode and e.body:
                    print(json.dumps(e.body, ensure_ascii=False))
                raise e
            except Exception as e:
                print(f"\n[Runtime Error] {e}")
                raise e