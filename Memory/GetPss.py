import os
import re
import shutil
import datetime
import subprocess
import time
import matplotlib.pyplot as plt
import seaborn as sns
import math
from scipy.stats import norm

current_run_index = 0
max_run = 30
max_count_per_run = 10

wait_launch_time = 40 
wait_next_time = 10
pss_interval = 5

package_name = 'todo' 
start_game = 'adb shell am start -n {}/{}.todo'.format(package_name, package_name)
end_game = 'adb shell am force-stop {}'.format(package_name)

folder = "todo"

# Get the data
# while current_run_index < max_run:
#     print("Loop Count: " + str(current_run_index))

#     os.system(start_game)
#     time.sleep(wait_launch_time)

#     current_index_in_one_run = 0
#     while current_index_in_one_run < max_count_per_run:
#         os.system("adb shell dumpsys meminfo {} > {}/{}-{}.log".format(package_name, folder, current_run_index,current_index_in_one_run))
#         current_index_in_one_run = current_index_in_one_run + 1
#         time.sleep(pss_interval)
    
#     os.system(end_game)

#     current_run_index = current_run_index + 1
#     time.sleep(wait_next_time)

# deal with data
data = {}

for filename in os.listdir(folder):
    with open(os.path.join(folder, filename), 'r') as f:
        for line in f:
            if 'TOTAL' in line:
                data[filename] = int(line.split()[1])

sorted_data = sorted(data.items(), key=lambda x: x[1])

num_elements_to_remove = int(len(sorted_data) * 0.05)
filtered_data = sorted_data[num_elements_to_remove:-num_elements_to_remove]

mid_index = len(filtered_data) // 2
median_pss = filtered_data[mid_index][1]
median_filename = filtered_data[mid_index][0]

pss_values = [pss for _, pss in filtered_data]
mean_pss = sum(pss_values) / len(pss_values)
variance_pss = sum((x - mean_pss) ** 2 for x in pss_values) / len(pss_values)

std_dev_pss = math.sqrt(sum((x - mean_pss) ** 2 for x in pss_values) / len(pss_values))
sample_size = len(pss_values)
z_score = norm.ppf(0.975)
margin_error = z_score * (std_dev_pss / math.sqrt(sample_size))
ci_lower = mean_pss - margin_error
ci_upper = mean_pss + margin_error

print(folder)
print(f"Average PSS: {mean_pss}")
print(f"Median PSS: {median_pss}, Filename: {median_filename}")
print(f"Standard Deviation PSS: {math.sqrt(variance_pss)}")
print(f"95% Confidence Interval: ({ci_lower}, {ci_upper})")