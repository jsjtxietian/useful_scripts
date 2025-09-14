import os
import re
import shutil
import datetime
import subprocess
import time
import matplotlib.pyplot as plt
import seaborn as sns

current_index = 0
max_count = 30
wait_launch_time = 50
wait_next_time = 10
dst_folder = "todo"

get_log_record_list = 'for /f "delims=" %a in (\'adb shell find /storage/emulated/0/Android/data/todo/files/ -name "todo.todo"\') do adb pull "%a" {0}'.format(dst_folder)

package_name = 'todo'
start_game = 'adb shell am start -n {}/{}.todo'.format(package_name, package_name)
end_game = 'adb shell am force-stop {}'.format(package_name)
command = "adb logcat -s Unity"

def calc_average_time(path,keywords):
    numbers = {}

    for filename in os.listdir(path):
        with open(os.path.join(path, filename), 'r') as f:
            for line in f:
                for keyword in keywords:
                    if keyword in line:
                        numbers.setdefault(keyword, []).append(int(line.split(':')[-1]))
    
    with open(dst_folder + "result.txt", 'w') as f:
        for key in numbers:
            values = numbers[key] 
            average = sum(values) / len(values)  
            result = f"{key}: {average:.2f} (sample num: {len(values)})"
            print(result)
            f.write(result + "\n")

            # can also draw something here
            # fig, ax = plt.subplots()
            # ax.plot(values)
            # ax.set_title(key)
            # sns.displot(values)
            # plt.show()
        f.close()
    


def get_average_time(keywords):
    if os.path.exists(dst_folder):
        shutil.rmtree(dst_folder)
    os.makedirs(dst_folder)
    
    while current_index < max_count:
        start_app()
        time.sleep(wait_launch_time)
        clear_app()
        time.sleep(wait_next_time)
    os.system(get_log_record_list)
    
    time.sleep(20)

    calc_average_time(dst_folder,keywords)
    


def start_app():
    global current_index 
    print("Loop Count: " + str(current_index))
    current_index = current_index + 1
    os.system(start_game)

def clear_app():
    os.system(end_game)
    os.system("adb logcat -c")

def filter_logcat():
    p_obj = subprocess.Popen(
            args=command,
            stdin=None, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False)
    print("Logcat catching and filtering...")
    with p_obj:
        for line in p_obj.stdout:
            print(line)
    #p_obj.kill()
    #p_obj.wait()


get_average_time(["todo_tag1","todo_tag2"])

