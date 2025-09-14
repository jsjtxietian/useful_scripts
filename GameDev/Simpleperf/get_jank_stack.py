import json

def resolve_stack(stack_index, stack_table_data, frame_table_data, string_table, stack_schema, frame_schema):
    """
    Recursively resolves a stack table entry into a list of frame strings.
    
    Returns a list of frame strings from bottom (root) to top.
    """
    if stack_index is None:
        return []
    entry = stack_table_data[stack_index]
    prefix_index = entry[stack_schema.get("prefix", 0)]
    frame_idx = entry[stack_schema.get("frame", 1)]
    
    frames = []
    if prefix_index is not None:
        frames.extend(resolve_stack(prefix_index, stack_table_data, frame_table_data, string_table, stack_schema, frame_schema))
    
    frame_record = frame_table_data[frame_idx]
    location_idx = frame_record[frame_schema.get("location", 0)]
    frame_str = string_table[location_idx] if 0 <= location_idx < len(string_table) else "<unknown>"
    frames.append(frame_str)
    
    return frames

# Load the original JSON profile.
with open("1.json", "r") as f:
    profile = json.load(f)

# Compute the global minimum sample time across all threads.
global_times = []
for thread in profile.get("threads", []):
    samples = thread.get("samples", {})
    sample_data = samples.get("data", [])
    sample_schema = samples.get("schema", {})
    time_idx = sample_schema.get("time", 1)
    for sample in sample_data:
        global_times.append(sample[time_idx])
global_min_time = min(global_times) if global_times else 0

# --- Detect the first Big Jank event in the "UnityGfxDeviceW" thread ---
target_thread_name = "UnityGfxDeviceW"
gfx_thread = next((t for t in profile.get("threads", []) if t.get("name") == target_thread_name), None)
if gfx_thread is None:
    print(f"Thread '{target_thread_name}' not found.")
    exit(1)

# Retrieve samples and schema from UnityGfxDeviceW.
samples = gfx_thread.get("samples", {})
sample_data = samples.get("data", [])
sample_schema = samples.get("schema", {})
time_idx_field = sample_schema.get("time", 1)
stack_idx_field = sample_schema.get("stack", 0)

# Get stackTable, frameTable, and stringTable for the thread.
stack_table = gfx_thread.get("stackTable", {}).get("data", [])
stack_table_schema = gfx_thread.get("stackTable", {}).get("schema", {"prefix": 0, "frame": 1})
frame_table = gfx_thread.get("frameTable", {}).get("data", [])
frame_table_schema = gfx_thread.get("frameTable", {}).get("schema", {"location": 0})
string_table = gfx_thread.get("stringTable", [])

# Compute relative time for each sample and detect frame-end events based on "eglSwapBuffers".
frame_events = []  # Stores relative_time values when a frame end is detected.
prev_frame_event = False

for sample in sample_data:
    sample_time = sample[time_idx_field]
    relative_time = int(sample_time - global_min_time)
    sample_stack_index = sample[stack_idx_field]
    
    if sample_stack_index is not None and stack_table:
        stack_frames = resolve_stack(sample_stack_index, stack_table, frame_table, string_table,
                                     stack_table_schema, frame_table_schema)
        # We create the reversed stack array (for our detection we only need to check its content).
        reversed_stack_array = list(reversed(stack_frames))
    else:
        reversed_stack_array = []
    
    # If any frame in the reversed stack contains "eglSwapBuffers", consider it a frame end.
    if any("eglSwapBuffers" in frame for frame in reversed_stack_array):
        if not prev_frame_event:
            frame_events.append(relative_time)
            prev_frame_event = True
    else:
        prev_frame_event = False

num_frames = len(frame_events)
frame_times = [frame_events[i] - frame_events[i-1] for i in range(1, num_frames)]

# Identify the first Big Jank event.
first_big_jank_index = None
for i in range(3, len(frame_times)):
    avg_prev = sum(frame_times[i-3:i]) / 3.0
    if frame_times[i] > 2 * avg_prev and frame_times[i] > 125:
        first_big_jank_index = i + 1  # frame_events index corresponding to the big jank
        break

if first_big_jank_index is None:
    print("No big jank event found.")
    exit(1)

# Define the Big Jank period.
big_jank_start_time = frame_events[first_big_jank_index - 1]
big_jank_end_time = frame_events[first_big_jank_index]
print(f"Big Jank period (relative time): {big_jank_start_time} ms to {big_jank_end_time} ms")

# --- Truncate the samples in the original JSON for all threads ---
# For each thread, we only keep the samples whose relative time is within the Big Jank period.
for thread in profile.get("threads", []):
    samples = thread.get("samples", {})
    sample_data = samples.get("data", [])
    sample_schema = samples.get("schema", {})
    time_idx_field = sample_schema.get("time", 1)
    
    new_sample_data = []
    for sample in sample_data:
        sample_time = sample[time_idx_field]
        relative_time = int(sample_time - global_min_time)
        # Keep sample if it falls within the Big Jank period.
        if big_jank_start_time <= relative_time <= big_jank_end_time:
            # Adjust time: new time = original relative time - big_jank_start_time (so period starts at 0).
            new_time = relative_time - big_jank_start_time
            new_sample = list(sample)  # copy the sample array
            new_sample[time_idx_field] = new_time
            new_sample_data.append(new_sample)
    
    # Update the samples field in the thread.
    samples["data"] = new_sample_data
    thread["samples"] = samples

# The meta part remains unchanged.
# Save the truncated JSON to a new file.
with open("truncated_profile.json", "w") as f:
    json.dump(profile, f, indent=2)

print("Truncated JSON profile saved as 'truncated_profile.json'.")
