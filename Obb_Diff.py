import bsdiff4
import os
import subprocess
import shutil
import UnityPy
import filecmp
import csv

# fill this three variable
library_meta = (
    "todo/Library/metadata"
)
old_folder = "left obb file unziped folder name"
new_folder = "right obb file unziped folder name"

# global variable
shared_content_old = {}
shared_content_new = {}
temp_merge = "temp_merge"

def get_file_type(file_name):
    if "level" in file_name:
        return "level"
    if ".assets" in file_name:
        return "shared assets"
    return "guid"


def read_data(path):
    with open(path, "rb") as fi:
        data = fi.read()
    return data


def try_unify_split(file_name):
    # no origin, only split0,1,2...
    if ".split0" in file_name and not os.path.exists(file_name.replace(".split0", "")):
        with open(temp_merge, "wb") as temp:
            input = []
            input.append(open(file_name, "rb").read())

            base_name = file_name.replace(".split0", "")
            index = 1
            # find all split1,2...
            while os.path.exists(base_name + ".split" + str(index)):
                input.append(open(base_name + ".split" + str(index), "rb").read())
                index = index + 1

            for i in input:
                temp.write(i)
        file_name = temp_merge
        return file_name
    # origin and split0,1,2...
    elif os.path.exists(file_name + ".split0"):
        with open(temp_merge, "wb") as temp:
            input = []
            input.append(open(file_name, "rb").read())

            index = 0
            # find all split0,1,...
            while os.path.exists(file_name + ".split" + str(index)):
                input.append(open(file_name + ".split" + str(index), "rb").read())
                index = index + 1

            for i in input:
                temp.write(i)
        file_name = temp_merge
        return file_name
    else:
        return file_name


def get_assets_in_shared(file_name):
    content = ""
    file_name = try_unify_split(file_name)

    env = UnityPy.load(file_name)
    for obj in env.objects:
        if obj.type.name in [
            "Texture2D",
            "Sprite",
            "TextAsset",
            "MonoBehaviour",
            "GameObject",
            "AudioClip",
            "Font",
            "Mesh",
            "Shader",
            "Material",
        ]:
            try:
                data = obj.read()
                content = content + "{0}({1});".format(data.name, obj.type.name)
            except:
                content = content + "NoName({0});".format(obj.type.name)
    
    # cache the result for later use
    is_old = old_folder in file_name
    if content != "" :
        simple_name = file_name[file_name.find("\\")+1:]
        if is_old:
            shared_content_old[simple_name] = content
        else:
            shared_content_new[simple_name] = content
    
    return content


def get_asset_path(guid):
    if ".resource" in guid:
        guid = guid.replace(".resource", "")
    guid = guid[-32:]

    info = os.path.join(library_meta, guid[0:2], guid + ".info")
    try:
        with open(info, "rb") as file:
            content = file.read()
            path_location = content.find(b"path:")
            if path_location != -1:
                next_line_end = content.find(b"\n", path_location)
                data = content[path_location:next_line_end].decode()
                data = data[5:].strip()
                return data
            else:
                return ""

    except OSError as exc:
        return ""


def get_scene_name(file_name):
    result = ""
    with open(file_name, "rb") as file:
        content = file.read()
        # todo: get scene name in binary content
        # path_location = content.find(b"your scene name")
        # next_line_end = content.find(0b00000000, path_location)
        # data = content[path_location:next_line_end].decode()
        # result = data.strip()
    return result


def get_file_content(file_name):
    file_type = get_file_type(file_name)
    if file_type == "guid":
        return get_asset_path(file_name)
    elif file_type == "level":
        return get_scene_name(file_name)
    elif file_type == "shared assets":
        return get_assets_in_shared(file_name)


def get_shrink_content(content):
    if len(content) > 200:
        content = content[:200] + "..."
    return content


def detailed_report(old_obb, new_obb):
    output_report = "{0}_{1}_diff_report.csv".format(old_obb, new_obb)
    output = open(output_report, "w+")
    output.write(
        "file_type,file_name,bsdiff_size(bytes),content_same,{0}_content,{1}_content\n".format(
            old_obb, new_obb
        )
    )

    g = os.walk(os.path.join(new_obb, "assets\\bin\\Data\\"))
    for path, die_list, file_list in g:
        for file_name in file_list:
            right_name = os.path.join(path, file_name)
            file_type = get_file_type(right_name)
            right_content = get_file_content(right_name)

            left_name = os.path.join(old_obb, "assets\\bin\\Data", file_name)

            if os.path.exists(left_name):
                left_content = get_file_content(left_name)

                content_same = left_content == right_content
                if left_content == "" and right_content == "":
                    content_same = ""

                diff_size = ""
                if filecmp.cmp(left_name, right_name):
                    diff_size = "Identical"
                    content_same = True
                else:
                    diff_size = len(
                        bsdiff4.diff(read_data(left_name), read_data(right_name))
                    )
                output.write(
                    "{0},{1},{2},{3},{4},{5}\n".format(
                        file_type,
                        file_name,
                        diff_size,
                        content_same,
                        ""
                        if content_same == True
                        else get_shrink_content(left_content),
                        get_shrink_content(right_content),
                    )
                )
            else:
                output.write(
                    "{0},{1},{2},{3},{4},{5}\n".format(
                        file_type,
                        file_name,
                        "new file | raw size bytes:{0}".format(
                            os.path.getsize(right_name)
                        ),
                        False,
                        "",
                        get_shrink_content(right_content),
                    )
                )
    output.close()
    # if os.path.exists(temp_merge):
    #     os.remove(temp_merge)
    return output_report


def get_resource_type(path):
    res_type = "Unknown"
    file_suffix = "Unknown"

    if path == "":
        return (res_type, file_suffix)

    # todo, determine resource path by path, somehing like:
    # if "Audio/" in path:
        # res_type = "Audio"

    file_suffix = path[path.rfind(".") + 1 :]
    if len(file_suffix) > 10:
        file_suffix = "Unknown"
    return (res_type, file_suffix)


def check_and_insert_pair(dictionary, key, value):
    if key in dictionary:
        dictionary[key].append(value)
    else:
        dictionary[key] = [value]

def convert_byte_2_kb(byte):
    return round(float(byte) / 1024,2)

def predict_size(size_add,size_change):
    output_report = "update predict.txt"
    compression_rate = 0.6
    with open(output_report, "w+") as output:
        size_add = convert_byte_2_kb(size_add) / 1024
        size_change = convert_byte_2_kb(size_change) / 1024
        total =  size_add * compression_rate + size_change
        output.write("raw add size: {0} mb\n".format(round(size_add,2)))
        output.write("change size: {0} mb\n".format(round(size_change,2)))
        output.write("assuming compression_rate is {0}\n".format(compression_rate))
        output.write("predict update size for obb: {0} mb\n".format(round(total,2)))


def write_dic_to_file(table, title):
    output_report = "{0}.txt".format(title)
    with open(output_report, "w+") as output:
        output.write("======================================\n")
        output.write(title + "\n")

        detailed_info = []
        outline_info = []

        for key in table:
            table[key].sort(reverse=True)
            updated_size = 0
            for value in table[key]:
                updated_size += value[0]

            summary = "{0} kb in total, Category {1}\n".format(convert_byte_2_kb(updated_size), key)
            detailed = summary

            outline_info.append((updated_size, summary))
            for value in table[key]:
                detailed = detailed + "{0}, {1}\n".format(convert_byte_2_kb(value[0]), value[1])
            detailed = detailed + "\n\n"
            detailed_info.append(((updated_size, detailed)))

        outline_info.sort(reverse=True)
        output.write("\nSummary:\n")
        for o in outline_info:
            output.write(o[1])

        detailed_info.sort(reverse=True)
        output.write("\nDetailed:\n")
        for d in detailed_info:
            output.write(d[1])

        output.write("======================================\n")


def get_statistics(report_name):
    csv_reader = csv.reader(open(report_name))

    type_add_table = {}
    type_change_table = {}
    suffix_add_table = {}
    suffix_change_table = {}

    size_add = 0
    size_change = 0

    for line in csv_reader:
        diff_state = line[2]
        path = line[5]
        if "Identical" in diff_state:
            continue
        if line[0] == "guid":
            res_type, file_suffix = get_resource_type(path)
            if path == "":
                path = line[1]
            if "new file" in diff_state:
                size = int(diff_state[diff_state.find(":") + 1 :])
                check_and_insert_pair(type_add_table, res_type, (size, path))
                check_and_insert_pair(suffix_add_table, file_suffix, (size, path))
            else:
                size = int(diff_state)
                check_and_insert_pair(type_change_table, res_type, (size, path))
                check_and_insert_pair(suffix_change_table, file_suffix, (size, path))
        
        if "new file" in diff_state:
            size_add = size_add + int(diff_state[diff_state.find(":") + 1 :])
        elif diff_state.isdigit():
            size_change = size_change + int(diff_state)

    write_dic_to_file(type_add_table, "resources added, categorized by type")
    write_dic_to_file(suffix_add_table, "resources added, categorized by suffix")
    write_dic_to_file(type_change_table, "resources changed, categorized by type")
    write_dic_to_file(suffix_change_table, "resources changed, categorized by suffix")

    predict_size(size_add,size_change)
    

def main():
    detailed_report_name = detailed_report(old_folder, new_folder)
    get_statistics(detailed_report_name)

main()