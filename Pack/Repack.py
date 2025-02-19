import os
import sys
import re
import shutil
import datetime
import subprocess
import threading
import time
import zipfile

# Config
push_localconf = False
need_adb_log = True
only_unity_log = True
need_replay = False
uninstall_previous = False
apk_name_no_suffix = ''
uncompress_resource = True

if len(sys.argv) == 2:
    apk_name_no_suffix = os.path.basename(sys.argv[1][:-4])
print(f"Use apk: {apk_name_no_suffix}.apk")

if not os.path.exists(f"{apk_name_no_suffix}.apk"):
    print("Apk not exist")
    exit(0)


dev = True if 'devel' in apk_name_no_suffix else False

apk_name = apk_name_no_suffix + '.apk'
base_path = 'todo'
engine_path = 'todo'
temp_path = './todo'
sign_command = 'java -jar todo/build-tools/32.0.0/lib/apksigner.jar sign todo'.format(apk_name)

# check connect phone's abi
abi = ""
subprocess.run(['adb', 'kill-server'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
check_abi_result = subprocess.run(['adb', 'shell', 'getprop', 'ro.product.cpu.abi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

if check_abi_result.returncode == 0:
    architecture = check_abi_result.stdout.strip()
    if 'arm64' in architecture:
        abi = 'arm64-v8a'
    elif 'armeabi' in architecture or 'x86' in architecture:
        abi = 'armeabi-v7a'

if abi == "":
    abi = 'armeabi-v7a'
    print("False back to abi: " + abi)
else:    
    print("Use connected phone's abi: " + abi)
print("Dev build: " + str(dev))

# other configs
so_path = 'build/AndroidPlayer/Variations/il2cpp/{}/Libs/{}/libunity.so'.format('Development' if dev else 'Release' ,abi)
build_command = "todo AndroidPlayer{}IL2CPP{} -sCONFIG=release".format("" if abi == 'armeabi-v7a' else "64", "" if dev else "NoDevelopment")

package_name = 'todo'
start_game = 'adb shell am start -n {}/{}.todo'.format(package_name, package_name)
clean_command = "adb kill-server"
logcat_command = "adb logcat -s Unity -v brief"
push_sth = 'adb push todo "/storage/emulated/0/Android/data/{}/todo"'.format(package_name)
kill_game = 'adb shell am force-stop {}'.format(package_name)

def capture_adb_log():
    os.system("adb logcat -c")
    with open("adb_log_output.log", "w") as file:
        subprocess.run(logcat_command, stdout=file, stderr=subprocess.STDOUT)

def compress_directory_with_uncompressed_resources_arsc(source_dir, zip_path):
    """
    1. Compress all files except `resources.arsc` with ZIP_DEFLATED.
    2. Reopen in append mode ('a') and add `resources.arsc` with ZIP_STORED.
    """
    # 1) Write everything except resources.arsc with compression
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for filename in files:
                if filename == 'resources.arsc':
                    # Skip for now; we'll add it uncompressed later.
                    continue
                filepath = os.path.join(root, filename)
                arcname = os.path.relpath(filepath, start=source_dir)
                zipf.write(filepath, arcname)

    # 2) If resources.arsc exists, add it uncompressed
    resources_path = os.path.join(source_dir, 'resources.arsc')
    if os.path.exists(resources_path):
        # Append mode
        with zipfile.ZipFile(zip_path, 'a') as zipf:
            # Create ZipInfo to specify per-file compression
            info = zipfile.ZipInfo('resources.arsc')
            info.compress_type = zipfile.ZIP_STORED  # no compression
            # Read the file’s data
            with open(resources_path, 'rb') as f:
                data = f.read()
            # Add it to the zip archive
            zipf.writestr(info, data)

def do():
    print('let\'s go!')
    
    os.chdir(engine_path)

    print('build_command is : ' + build_command)
    result = subprocess.run(build_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, encoding='utf-8')
    
    os.chdir(base_path)
    if "build success" in result.stdout:
        print('build engine so done')
    else:
        print(result.stdout)
        with open("buildlog.log", "a") as log_file:
            log_file.write(result.stdout)
        print('build engine so failed, see buildlog.log')
        return

    if not os.path.exists(temp_path):
        with zipfile.ZipFile(apk_name, 'r') as zip_ref:
            zip_ref.extractall(temp_path)
        print('unzip done')
    else:
        print('unzip skipped')

    new_so = os.path.join(engine_path,so_path)
    current_so = os.path.join(base_path,'temp_extracted_apk','lib/{}/libunity.so'.format(abi))
    shutil.copy(new_so, current_so)
    print('copy {} so from {} to {} done'.format(abi, new_so, current_so))

    if os.path.exists(apk_name):
        os.remove(apk_name)
        print('remove origin apk file done')
    else:
        print("can't find origin apk, skipped")

    if uncompress_resource:
        compress_directory_with_uncompressed_resources_arsc(temp_path, apk_name_no_suffix + '.zip')
        os.rename(apk_name_no_suffix + '.zip', unaligned_name)
         # https://github.com/mathieures/convert-apk
        os.system(zipalign_command)
        os.remove(unaligned_name)
        print('zipalign done')
    else:
        shutil.make_archive(apk_name_no_suffix, 'zip', temp_path)
        os.rename(apk_name_no_suffix + '.zip', apk_name)

    print('re zip done')

    os.system(sign_command)
    print('sign done')

    os.system(clean_command)
    os.system(kill_game)

    if uninstall_previous:
        os.system('adb uninstall {0}'.format(package_name))
        print('uninstall previous apk done')

    os.system('adb install -g {0}'.format(apk_name))
    print('install new apk done')

    if need_push_sth:
        if os.path.exists("todo"):
            os.system(push_sth)
            print('push sth done')

    print('start game')
    os.system(start_game)

    if need_adb_log:
        print('capturing adb log and start game')
        capture_adb_log()

do()

