import subprocess
import time
import psutil

g_device_id = 'todo'
g_package_name = 'todo'
g_waitTime = 5
g_unit = 1024 * 1024

def get_page_size(device_id):
    page_size = 0
    get_page_size_cmd = 'adb shell getconf PAGESIZE'.format(device_id)
    result = subprocess.run(get_page_size_cmd, shell=True, capture_output=True)
    if result.returncode == 0:
        page_size = result.stdout.decode().strip()
        page_size = int(page_size)
        print("Page Size:", page_size)
    else:
        error = result.stderr.decode().strip()
        print("get_page_size Error:", error)
        print("Let's suppose page size is 4KB")
        page_size = 4 * 1024
    return page_size

def get_pid(package_name):
    pid = 0
    get_pid_cmd = 'adb shell pidof {}'.format(package_name)
    result = subprocess.run(get_pid_cmd, shell=True, capture_output=True)
    if result.returncode == 0:
        pid = result.stdout.decode().strip()
        print("Pid:", pid)
    else:
        error = result.stderr.decode().strip()
        print("get_pid Error:", error)
    return pid

def get_statm_out(pid):
    ret = None
    get_statm_out_cmd = 'adb shell cat /proc/{}/statm'.format(pid)
    result = subprocess.run(get_statm_out_cmd, shell=True, capture_output=True)
    if result.returncode == 0:
        statm_out = result.stdout.decode().strip()
        statm_out_arry = statm_out.split(' ')
        vss_page_num = statm_out_arry[0]
        pss_page_num = statm_out_arry[1]
        ret = [vss_page_num, pss_page_num]
    else:
        error = result.stderr.decode().strip()
        print("get_statm_out Error:", error)
    return ret


def main():
    page_size = get_page_size(g_device_id)
    if page_size == 0:
        return

    pid = get_pid(g_package_name)
    if pid == 0:
        return

    max_vss = 0
    max_pss = 0
    while True:
        vp = get_statm_out(pid)
        if vp is None:
            return

        vss_page_name = int(vp[0])
        pss_page_name = int(vp[1])
        vss = vss_page_name * page_size / g_unit
        pss = pss_page_name * page_size / g_unit
        max_vss = max(max_vss, vss)
        max_pss = max(max_pss, pss)
        print('VSS {} MB, PSS {} MB, MAX VSS {}, MAX PSS {}'.format(vss, pss, max_vss, max_pss))
        time.sleep(g_waitTime)

    return

main()

