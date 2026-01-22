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
                print("\n" + "="*40)
                print(f"{'序号':<4} | {'角色':<10} | {'消息内容'}")
                print("-" * 40)
                for i, msg in enumerate(manager.global_history):
                    # 限制显示长度以美化 CLI
                    content_preview = msg['content'].replace('\n', ' ')
                    print(f"{i:03d}  | {msg['role_name']:<10} | {content_preview}")
                print("="*40)

            elif cmd == "delete":
                if not args:
                    print("用法: delete <序号>")
                    continue
                try:
                    idx = int(args[0])
                    removed = manager.delete_message(idx)
                    if removed:
                        print(f"[成功] 已删除序号 {idx} 的消息: [{removed['role_name']}]: {removed['content'][:20]}...")
                    else:
                        print(f"[错误] 无效的序号: {idx}")
                except ValueError:
                    print("[错误] 序号必须是整数")

            elif cmd == "speak":
                if not args:
                    print("用法: speak <agent_id>")
                    continue
                agent_id = args[0]
                print(f"[*] 正在等待 {agent_id} ({manager.agents.get(agent_id).name if agent_id in manager.agents else '未知'}) 回复...")
                msg = await manager.agent_speak(agent_id)
                if msg:
                    print(f"\n[{msg['role_name']}]: {msg['content']}")

            elif cmd == "auto":
                if not args:
                    print("用法: auto <n>")
                    continue
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

            elif cmd == "export":
                name = args[0] if args else None
                path = manager.export_history(name)
                print(f"历史记录已导出至: {path}")

            elif cmd == "load":
                if not args:
                    print("用法: load <path>")
                    continue
                await manager.load_history(args[0])
                print(f"已成功加载历史并重同步 {len(manager.agents)} 个角色记忆。")

            elif cmd == "status":
                print("\n--- 角色状态与私有工具 ---")
                for aid, agent in manager.agents.items():
                    tools_str = ", ".join([t.name for t in agent.tools]) if agent.tools else "无"
                    print(f"ID: {aid:12} | 姓名: {agent.name:10} | 私有工具: {tools_str}")

            elif cmd == "help":
                print("""
指令列表:
  list / show   [新] 列出所有消息及其序号
  delete <n>    [新] 根据序号删除消息，并重置所有角色记忆到该状态
  speak <id>    强制指定 ID 为 <id> 的角色生成下一条回复
  auto <n>      按照 user.json 中的顺序自动循环对话 <n> 轮
  status        查看当前已加载的角色及其关联的私有工具
  export [name] 将当前对话状态保存至 ./history/[name].json
  load <path>   从指定文件导入对话记录并初始化所有角色状态
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