import N10X
import subprocess
import os
import webbrowser
import re
import threading

def run_git_blame_and_open_browser(file_path, line):
    command = ['git', 'blame','-M', '-C', '-C', '-L', f'{line},{line}', '--porcelain', '--', os.path.basename(file_path)]
    file_dir = os.path.dirname(file_path)
    result = subprocess.run(command, cwd=file_dir, capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    blame_output = result.stdout.decode('utf-8', errors='ignore')
    commit_hash = blame_output.split(' ', 1)[0]

    if not re.match(r'^[a-f0-9]{40}$', commit_hash):
        return
    url = f"https://github.com/EpicGames/UnrealEngine/commit/{commit_hash}"
    webbrowser.open(url)

def FindCommitInUE():
    file_path = N10X.Editor.GetCurrentFilename()
    if not file_path:
        return

    _, line = N10X.Editor.GetCursorPos()
    line = line + 1

    thread = threading.Thread(target=run_git_blame_and_open_browser, args=(file_path, line))
    thread.start()

    


