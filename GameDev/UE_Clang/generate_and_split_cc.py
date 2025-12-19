import os
import json
import subprocess
import sys

# ================= 配置区域 =================
# UBT 的绝对路径
UBT_PATH = r"D:\unrealengine5\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe"

# 您的 .uproject 文件路径
PROJECT_FILE = r"D:\P4\client\Product.uproject"

# 引擎根目录 (用于判定归属，以及存放拆分后的文件)
ENGINE_ROOT = r"D:\unrealengine5"

# 项目根目录 (用于判定归属，以及存放拆分后的文件)
PROJECT_ROOT = r"D:\P4\client"

# UBT 命令参数 (注意：Target名字 ProductEditor 需要根据实际情况确认)
UBT_ARGS = [
    UBT_PATH,
    "-Target=ProductEditor", 
    "Win64", 
    "Development", 
    f"-project={PROJECT_FILE}", 
    "-mode=GenerateClangDatabase"
]
# ===========================================

def normalize_path(path):
    """标准化路径分隔符，统一转为 / 并小写，方便比较"""
    return path.replace("\\", "/").lower()

def main():
    print(f"--- 1. 开始调用 UBT 生成 compile_commands.json ---")
    try:
        # 执行 UBT 命令
        subprocess.check_call(UBT_ARGS)
    except subprocess.CalledProcessError as e:
        print(f"错误: UBT 执行失败，错误码: {e.returncode}")
        sys.exit(1)
    
    # UBT 通常会把 json 生成在项目根目录
    possible_paths = [
        os.path.join(PROJECT_ROOT, "compile_commands.json"), # 优先找项目下
        os.path.join(ENGINE_ROOT, "compile_commands.json")   # 其次找引擎下
    ]
    
    source_json_path = None
    last_mtime = 0

    print("--- 2. 寻找最新生成的文件 ---")
    for p in possible_paths:
        if os.path.exists(p):
            mtime = os.path.getmtime(p)
            print(f"  发现文件: {p} (时间戳: {mtime})")
            # 找最新的
            if mtime > last_mtime:
                last_mtime = mtime
                source_json_path = p
    
    if not source_json_path:
        print(f"错误: 在以下路径均未找到 compile_commands.json:")
        for p in possible_paths:
            print(f" - {p}")
        sys.exit(1)


    print(f"--- 2. 开始解析并拆分 JSON ---")
    
    with open(source_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    engine_commands = []
    project_commands = []
    
    norm_engine_root = normalize_path(ENGINE_ROOT)
    
    # 统计计数
    total_count = len(data)
    
    for entry in data:
        # 获取源文件的路径
        file_path = normalize_path(entry.get('file', ''))
        
        # 判定逻辑：如果文件路径以引擎目录开头，归类为引擎；否则归类为项目
        if file_path.startswith(norm_engine_root):
            engine_commands.append(entry)
        else:
            # 包含 Game 逻辑和可能的插件逻辑
            project_commands.append(entry)

    print(f"总条目: {total_count}")
    print(f"引擎条目: {len(engine_commands)}")
    print(f"项目条目: {len(project_commands)}")

    # 写入引擎目录
    engine_output_path = os.path.join(ENGINE_ROOT, "compile_commands.json")
    print(f"--- 3. 写入引擎配置: {engine_output_path} ---")
    with open(engine_output_path, 'w', encoding='utf-8') as f:
        json.dump(engine_commands, f, indent=4)

    # 写入项目目录
    project_output_path = os.path.join(PROJECT_ROOT, "compile_commands.json")
    print(f"--- 4. 写入项目配置: {project_output_path} ---")
    with open(project_output_path, 'w', encoding='utf-8') as f:
        json.dump(project_commands, f, indent=4)

    print("--- 完成! ---")
    print("现在可以在 VS Code Workspace 中分别享受纯净的索引了。")

if __name__ == "__main__":
    main()