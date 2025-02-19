import json
import concurrent.futures

# Load the name translation table
file_path = "./gecko-profile.json"
translation_file_path = "./nameTranslation.txt"

translation_dict = {}
with open(translation_file_path, "r", encoding="utf-8") as f:
    for line in f:
        if "⇨" in line:
            obfuscated, readable = line.strip().split("⇨")
            translation_dict[obfuscated] = readable

# Function to translate obfuscated names
def translate_symbol(symbol):
    words = symbol.split("_")
    translated_words = [translation_dict.get(word, word) for word in words]
    return "_".join(translated_words)

# Process all threads in parallel with translated symbols
def process_thread_with_translation(thread):
    string_table = thread.get("stringTable", [])
    updated_strings = []

    for entry in string_table:
        updated_strings.append(translate_symbol(entry))

    thread["stringTable"] = updated_strings

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    # Use ThreadPoolExecutor to process threads in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(process_thread_with_translation, data.get("threads", []))

# Save the updated JSON with translated symbols
translated_file_path = "./gecko-profile-translated.json"
with open(translated_file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

