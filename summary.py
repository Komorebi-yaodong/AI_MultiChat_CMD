import pyperclip
import os


LangChain_MCP_DOC = "./langchain_mcp.md"
README = "./README.md"

CORE = [
    "./main.py",
    "./core/",
    "./config.example.json",
    "./user.example.json",
]


# 获取文件文本
def read_text(file_path,iscode = True):
    with open(file_path, 'r',encoding='utf-8') as file:
        if iscode:
            return f"```{file_path.split('.')[-1]}\n{file_path}\n"+file.read()+"\n```\n"
        else:
            return file.read()+"\n"


# 从置顶目录下获取文件文本
def get_text_from_dir(dir_path):
    text = ""
    for file in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file)
        if os.path.isfile(file_path) and (file.endswith(".md") or file.endswith(".py") or file.endswith(".json") or file.endswith(".html") or file.endswith(".css")):
            text += read_text(file_path)
    return text


def get_summary():
    langchain_mcp = read_text(LangChain_MCP_DOC,False)
    readme = read_text(README,False)

    core_text = ""
    for file in CORE:
        if os.path.isdir(file):
            core_text += get_text_from_dir(file)
        else:
            core_text += read_text(file)
    
    text = [
        "以下是当前项目的的README文件",
        readme,
        "以下是langchain mcp的官方文档",
        langchain_mcp,
        "以下是项目的核心代码",
        core_text,
        "不论你进行如何修改，一定保证不会破坏已有的功能，前端修改一定要保持相同的主题风格，并保证节省开发者工作量的原则，请给出完整的函数代码并告诉我在哪里进行覆盖，直接告诉我在哪里进行怎样的修改就好了，不用给出全部文件代码\n\n"
    ]

    return "\n".join(text)

if __name__ == "__main__":
    sum = get_summary()
    with open("result.txt", "w", encoding='utf-8') as file:
        file.write(sum)
    # 将内容发送到剪切板
    pyperclip.copy(sum)
    print("内容已复制到剪切板")