import os
import re

def remove_empty_thoughts(content):
    """
    使用正则表达式移除文件末尾的 'thoughts' 部分，更健壮。
    """
    # 查找所有可能是 "thoughts" 的标题行
    # re.IGNORECASE 使其对大小写不敏感, re.MULTILINE 使其能匹配每一行的开头(^)
    pattern = re.compile(r"^\s*#{1,6}\s+thoughts.*$", re.IGNORECASE | re.MULTILINE)
    
    matches = list(pattern.finditer(content))
    
    if not matches:
        return content

    # 获取最后一个匹配项
    last_match = matches[-1]
    
    # 检查这个匹配项之后是否只有空白字符
    content_after_match = content[last_match.end():]
    if content_after_match.strip() == '':
        # 如果是，则从这个标题开始，裁掉后面的所有内容
        return content[:last_match.start()].rstrip() + '\n'
        
    return content


def convert_obsidian_markdown(content):
    """
    使用状态标记(flag)来处理代码块，逻辑更清晰、直接。
    """
    lines = content.split('\n')
    new_lines = []
    in_code_block = False  # 状态标记：是否在代码块内部

    for i, current_line in enumerate(lines):
        # 1. 检查是否是代码块的开始或结束
        if current_line.strip().startswith('```'):
            in_code_block = not in_code_block  # 反转状态
            new_lines.append(current_line)
            continue  # 直接进入下一行

        # 2. 如果在代码块内部，直接添加原文并跳过
        if in_code_block:
            new_lines.append(current_line)
            continue

        # 3. 如果不在代码块内部，执行添加空行的逻辑
        new_lines.append(current_line)
        
        # 定义简单的规则：什么情况下“不”应该加空行
        stripped_line = current_line.strip()
        # 如果当前行是空的，或者是特殊的块级元素（标题、列表、引用等），则不加空行
        if not stripped_line or stripped_line.startswith(('#', '>', '|', '---', '***')) or \
           re.match(r'^(\*|\+|-|\d+\.)\s', stripped_line):
            continue

        # 查看下一行，如果下一行也存在且是普通文本，则在它们之间添加一个空行
        if i + 1 < len(lines):
            next_line = lines[i+1].strip()
            # 下一行是空的，或者是特殊块级元素，则不加空行
            if not next_line or next_line.startswith(('#', '>', '|', '---', '***', '```')) or \
               re.match(r'^(\*|\+|-|\d+\.)\s', next_line):
                continue
            
            new_lines.append('')

    return '\n'.join(new_lines).rstrip() + '\n'

def process_directory(source_dir, target_dir):
    """
    处理源目录中的所有 Markdown 文件，并将转换后的版本保存到目标目录。
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    processed_count = 0
    error_count = 0
    
    for root, dirs, files in os.walk(source_dir):
        relative_path = os.path.relpath(root, source_dir)
        target_subdir = os.path.join(target_dir, relative_path)
        
        if not os.path.exists(target_subdir):
            os.makedirs(target_subdir)
        
        for file in files:
            if file.endswith('.md'):
                source_file_path = os.path.join(root, file)
                target_file_path = os.path.join(target_subdir, file)
                
                print(f"处理中: {source_file_path}...")
                try:
                    with open(source_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    converted_content = remove_empty_thoughts(content)
                    converted_content = convert_obsidian_markdown(converted_content)
                    
                    with open(target_file_path, 'w', encoding='utf-8') as f:
                        f.write(converted_content)
                    
                    processed_count += 1
                except Exception as e:
                    print(f"  [错误] 处理 {source_file_path} 时发生错误: {e}")
                    error_count += 1
    
    print("\n转换完成!")
    print(f"成功处理文件数: {processed_count}")
    if error_count > 0:
        print(f"发生错误的文件数: {error_count}")


def main():
    source_directory = './Cards'
    target_directory = './Output'
    
    if not os.path.isdir(source_directory):
        print(f"错误: 源目录 '{source_directory}' 不存在或不是一个目录。")
        return
        
    print("开始转换...")
    print(f"源目录: {os.path.abspath(source_directory)}")
    print(f"目标目录: {os.path.abspath(target_directory)}")
    process_directory(source_directory, target_directory)


if __name__ == "__main__":
    main()