import asyncio
import sys
from core.manager import DialogueManager

async def main():
    manager = DialogueManager()
    print("--- MASS: Multi-Agent Scam Interaction Framework ---")
    print("正在初始化 Agent...")
    await manager.initialize_agents()
    
    # 打印初始角色状态
    print("\n[已加载角色]")
    for aid, agent in manager.agents.items():
        print(f" - ID: {aid:12} | 姓名: {agent.name}")
    
    print("\n系统就绪。输入 'help' 查看指令。")

    while True:
        try:
            cmd_input = input("\n>>> ").strip().split()
            if not cmd_input:
                continue
            
            cmd = cmd_input[0].lower()
            args = cmd_input[1:]

            if cmd == "exit":
                if manager.config.get("save_on_exit"):
                    path = manager.export_history()
                    print(f"已自动保存历史至: {path}")
                break

            elif cmd in ["list", "show"]:
                print("\n" + "="*60)
                print(f"{'序号':<4} | {'角色':<10} | {'属性':<8} | {'消息内容'}")
                print("-" * 60)
                for i, msg in enumerate(manager.global_history):
                    # 检查是否有工具调用
                    has_tools = "TOOL" if msg.get('internal_thoughts') else "TEXT"
                    content_preview = msg['content'].replace('\n', ' ')
                    # 截断过长内容
                    if len(content_preview) > 50:
                        content_preview = content_preview[:47] + "..."
                        
                    print(f"{i:03d}  | {msg['role_name']:<10} | {has_tools:<8} | {content_preview}")
                print("="*60)

            elif cmd == "delete":
                if not args:
                    print("用法: delete <序号>")
                    continue
                try:
                    idx = int(args[0])
                    removed = manager.delete_message(idx)
                    if removed:
                        has_tools = " (含工具调用)" if removed.get('internal_thoughts') else ""
                        print(f"[成功] 已删除序号 {idx}{has_tools}: [{removed['role_name']}]")
                    else:
                        print(f"[错误] 无效的序号: {idx}")
                except ValueError:
                    print("[错误] 序号必须是整数")

            elif cmd == "speak":
                if not args:
                    print("用法: speak <agent_id>")
                    continue
                agent_id = args[0]
                print(f"[*] 正在等待 {agent_id} 回复...")
                msg = await manager.agent_speak(agent_id)
                if msg:
                    print(f"\n[{msg['role_name']}]: {msg['content']}")
                    if msg.get('internal_thoughts'):
                        print(f"    (触发了 {len(msg['internal_thoughts'])//2} 次工具交互)")

            elif cmd == "auto":
                if not args:
                    print("用法: auto <n>")
                    continue
                try:
                    n = int(args[0])
                    agent_ids = list(manager.agents.keys())
                    if not agent_ids:
                        print("错误：没有角色。")
                        continue
                    
                    for i in range(n):
                        agent_id = agent_ids[i % len(agent_ids)]
                        print(f"[*] ({i+1}/{n}) {agent_id} 正在思考...")
                        msg = await manager.agent_speak(agent_id)
                        print(f"[{msg['role_name']}]: {msg['content']}")
                except ValueError:
                    print("参数错误")

            elif cmd == "export":
                name = args[0] if args else None
                path = manager.export_history(name)
                print(f"历史记录已导出至: {path}")

            elif cmd == "load":
                if not args:
                    print("用法: load <path>")
                    continue
                await manager.load_history(args[0])
                print(f"已成功加载历史 (包含工具调用数据)。")

            elif cmd == "status":
                print("\n--- 角色状态与私有工具 ---")
                for aid, agent in manager.agents.items():
                    tools_str = ", ".join([t.name for t in agent.tools_map.values()]) if agent.tools_map else "无"
                    print(f"ID: {aid:12} | 姓名: {agent.name:10} | 私有工具: {tools_str}")

            elif cmd == "help":
                print("""
指令列表:
  list / show   列出消息，标记 [TOOL] 表示该轮对话包含隐藏的工具调用
  delete <n>    删除序号 <n> 的消息 (及其关联的所有隐藏工具调用)
  speak <id>    强制指定 ID 为 <id> 的角色生成下一条回复
  auto <n>      按照 user.json 中的顺序自动循环对话 <n> 轮
  status        查看当前已加载的角色及其关联的私有工具
  export [name] 将当前对话状态保存至 ./history/[name].json
  load <path>   从指定文件导入对话记录
  exit          退出并根据配置自动保存
                """)
            else:
                print(f"未知指令: {cmd}，输入 help 查看帮助。")

        except KeyboardInterrupt:
            print("\n程序中断，正在退出...")
            break
        except Exception as e:
            print(f"\n[运行时错误]: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())