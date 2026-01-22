import asyncio
import json
import os
from openai import AsyncOpenAI, APIStatusError, APITimeoutError, APIConnectionError

# 读取 user.json 获取配置
def load_config():
    if not os.path.exists("user.json"):
        print("错误: 未找到 user.json 文件")
        return None
    
    with open("user.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        if not data:
            print("错误: user.json 为空")
            return None
        return data

async def test_connection():
    users = load_config()
    if not users:
        return

    # 默认测试第1个角色，你可以修改 index
    target_agent = users[0] 
    
    print("=" * 50)
    print("API 连通性测试 (Test Connectivity)")
    print("=" * 50)
    print(f"测试角色: {target_agent.get('name')} (ID: {target_agent.get('id')})")
    print(f"Base URL: {target_agent.get('base_url')}")
    print(f"Model   : {target_agent.get('model')}")
    # 稍微脱敏显示 Key
    key = target_agent.get('api_key', '')
    masked_key = key[:8] + "****" + key[-4:] if len(key) > 12 else "****"
    print(f"API Key : {masked_key}")
    print("-" * 50)

    client = AsyncOpenAI(
        api_key=target_agent.get("api_key"),
        base_url=target_agent.get("base_url"),
        timeout=20.0,
        max_retries=1
    )

    # 构造最简单的 Payload，不带任何 System Prompt 注入，纯粹测试 Hello
    messages = [
        {"role": "user", "content": "Hello, confirm you are online."}
    ]

    print("\n[1/2] 正在发送测试请求...")
    try:
        response = await client.chat.completions.create(
            model=target_agent.get("model"),
            messages=messages,
            stream=False 
        )
        
        print("\n[2/2] ✅ 请求成功！")
        print(f"响应内容: {response.choices[0].message.content}")
        print("-" * 50)
        print("结论: API 配置有效，网络连接正常。")

    except APIStatusError as e:
        print(f"\n[2/2] ❌ API 状态错误 (HTTP {e.status_code})")
        print(f"错误信息: {e.message}")
        print("-" * 20 + " Error Body " + "-" * 20)
        # 尝试美化打印 JSON Body
        if e.body:
            try:
                print(json.dumps(e.body, ensure_ascii=False, indent=2))
            except:
                print(e.body)
        print("-" * 50)
        print("结论: 请求到达了服务器，但被拒绝。请检查 API Key、权限或模型名称是否正确。")
        print("如果是 403 Blocked，通常是服务商的防火墙拦截了 Python 的 User-Agent 或 IP。")

    except APIConnectionError as e:
        print(f"\n[2/2] ❌ 连接错误")
        print(f"详细信息: {str(e)}")
        print("-" * 50)
        print("结论: 无法连接到 Base URL。请检查 URL 拼写、代理设置或防火墙。")

    except Exception as e:
        print(f"\n[2/2] ❌ 未知错误")
        print(f"类型: {type(e).__name__}")
        print(f"信息: {str(e)}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_connection())