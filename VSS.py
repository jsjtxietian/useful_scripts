import subprocess
import time
import psutil
import sys
import os
import re
import json

SMapsMemInfos = {}

class SMaps_MemInfo:
    MemRange = ""
    TriggerPath = ""
    OriginalInfo = []
    Name = ""
    Size = 0
    KernelPageSize = 0
    MMUPageSize = 0
    Rss = 0
    Pss = 0
    Shared_Clean = 0
    Shared_Dirty = 0
    Private_Clean = 0
    Private_Dirty = 0
    Referenced = 0
    Anonymous = 0
    LazyFree = 0
    AnonHugePages = 0
    ShmemPmdMapped = 0
    Shared_Hugetlb = 0
    Private_Hugetlb = 0
    Swap = 0
    SwapPss = 0
    Writeback = 0
    Locked = 0
    THPeligible = 0
    VmFlags = ""

    def __init__(self):
        self.MemRange = ""
        self.TriggerPath = ""
        self.OriginalInfo = []
        self.Name = ""
        self.Size = 0
        self.KernelPageSize = 0
        self.MMUPageSize = 0
        self.Rss = 0
        self.Pss = 0
        self.Shared_Clean = 0
        self.Shared_Dirty = 0
        self.Private_Clean = 0
        self.Private_Dirty = 0
        self.Referenced = 0
        self.Anonymous = 0
        self.LazyFree = 0
        self.AnonHugePages = 0
        self.ShmemPmdMapped = 0
        self.Shared_Hugetlb = 0
        self.Private_Hugetlb = 0
        self.Swap = 0
        self.SwapPss = 0
        self.Writeback = 0
        self.Locked = 0
        self.THPeligible = 0
        self.VmFlags = ""

    def to_dict(self):
        return {
            'Name': self.Name,
            'Size': self.Size,
            'TriggerPath': self.TriggerPath,
            'MemRange': self.MemRange,
            'KernelPageS': self.KernelPageSize,
            'MMUPageSize': self.MMUPageSize,
            'Rss': self.Rss,
            'Pss': self.Pss,
            'Shared_Clea': self.Shared_Clean,
            'Shared_Dirty': self.Shared_Dirty,
            'Private_Clean': self.Private_Clean,
            'Private_Dirty': self.Private_Dirty,
            'Referenced': self.Referenced,
            'Anonymous': self.Anonymous,
            'LazyFree': self.LazyFree,
            'AnonHugePages': self.AnonHugePages,
            'ShmemPmdMapped': self.ShmemPmdMapped,
            'Shared_Hugetlb': self.Shared_Hugetlb,
            'Private_Hugetlb': self.Private_Hugetlb,
            'Swap': self.Swap,
            'SwapPss': self.SwapPss,
            'Writeback': self.Writeback,
            'Locked': self.Locked,
            'THPeligible': self.THPeligible,
            'VmFlags': self.VmFlags,
            'OriginalInfo': self.OriginalInfo
        }

    def UnSerialize(self, lines, start_index):
        i = start_index
        first_line_splits = lines[i].split(' ')
        self.MemRange = first_line_splits[0]
        self.OriginalInfo.append(lines[i])
        trigger_path = first_line_splits[len(first_line_splits)-1]
        if trigger_path.startswith('/'):
            self.TriggerPath = trigger_path
        i = i + 1
        end_index = i
        while i < len(lines):
            cur_line = lines[i]
            if cur_line.startswith("Name:"):
                self.Name = cur_line.split('Name:')[1].strip()
            elif cur_line.startswith("Size:"):
                self.Size = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("KernelPageSize:"):
                self.KernelPageSize = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("MMUPageSize:"):
                self.MMUPageSize = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Rss:"):
                self.Rss = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Pss:"):
                self.Pss = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Shared_Clean:"):
                self.Shared_Clean = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Shared_Dirty:"):
                self.Shared_Dirty = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Private_Clean:"):
                self.Private_Clean = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Private_Dirty:"):
                self.Private_Dirty = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Referenced:"):
                self.Referenced = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Anonymous:"):
                self.Anonymous = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("LazyFree:"):
                self.LazyFree = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("AnonHugePages:"):
                self.AnonHugePages = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("ShmemPmdMapped:"):
                self.ShmemPmdMapped = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Shared_Hugetlb:"):
                self.Shared_Hugetlb = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Private_Hugetlb:"):
                self.Private_Hugetlb = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Swap:"):
                self.Swap = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("SwapPss:"):
                self.SwapPss = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Writeback:"):
                self.Writeback = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("Locked:"):
                self.Locked = UnPackMemSize(cur_line.split(':')[1])
            elif cur_line.startswith("THPeligible:"):
                self.LazyFree = float(cur_line.split(':')[1].strip())
            elif cur_line.startswith("VmFlags:"):
                self.VmFlags = cur_line.split(':')[1].strip()
                end_index = i + 1
                break
            i = i + 1
            end_index = i
            self.OriginalInfo.append(cur_line)
            if end_index-start_index > 100:
                print("Some thing error start_index {} end_index {}", start_index, end_index)
        if len(self.Name) == 0:
            self.Name = "Path:"+self.TriggerPath
        return end_index

class SMaps_MemInfo_Group:
    MemInfos = []
    Total_Pss = 0
    Total_Vss = 0
    Name = ""
    def __init__(self, name):
        self.MemInfos = []
        self.Total_Pss = 0
        self.Total_Vss = 0
        self.Name = name

    def AppendMemInfo(self, mem_info):
        self.MemInfos.append(mem_info)
        self.Total_Vss = self.Total_Vss + mem_info.Size
        self.Total_Pss = self.Total_Pss + mem_info.Pss

    def to_dict(self):
        return {
            'Name': self.Name,
            'Total_Vss': self.Total_Vss,
            'Total_Pss': self.Total_Pss,
            'MemInfos_Count': len(self.MemInfos),
            'MemInfos': [mem_info.to_dict() for mem_info in self.MemInfos]
        }
def UnPackMemSize(line):
    result = 0
    splits = line.strip(' ').split(' ')
    result = float(splits[len(splits)-2])
    return result

def UnSerializeSamps(lines):
    global SMapsMemInfos
    SMapsMemInfos.clear()
    i = 0
    while i < len(lines):
        cur_mem_info = SMaps_MemInfo()
        i = cur_mem_info.UnSerialize(lines, i)
        if cur_mem_info.Name in SMapsMemInfos:
            SMapsMemInfos[cur_mem_info.Name].AppendMemInfo(cur_mem_info)
        else:
            group = SMaps_MemInfo_Group(cur_mem_info.Name)
            group.AppendMemInfo(cur_mem_info)
            SMapsMemInfos[cur_mem_info.Name] = group
			
def ConvertToJson(foler, filename):
    file_path = os.path.join(foler, filename)

    dump_file = open(file_path, "r", encoding="utf-8")
    file_lines = dump_file.readlines()
    UnSerializeSamps(file_lines)
	
    mem_groups = SMapsMemInfos.values()
    sorted_mem_groups = sorted(mem_groups, key=SortByGroupVSS, reverse=True)
    for m in sorted_mem_groups:
        m.MemInfos = sorted(m.MemInfos,key=lambda x:x.Size, reverse=True)
    out_list = []
    for group in sorted_mem_groups:
        out_list.append(group.to_dict())
    json_str = json.dumps(out_list, indent=4)   
    
    file_name_without_extension = os.path.splitext(os.path.basename(filename))[0]
    dump_file = open(os.path.join(foler, "json", file_name_without_extension) + '.json', 'w', encoding='utf-8')
    dump_file.write(json_str)		

def SortByGroupVSS(element):
    return element.Total_Vss

def GetAllVss(foler, filename):
    file_path = os.path.join(foler, filename)
    smaps_content = open(file_path, "r", encoding="utf-8").read()
    size_pattern = re.compile(r'^Size:\s+(\d+)\s+kB$', re.MULTILINE)
    # size_pattern = re.compile(r'^Pss:\s+(\d+)\s+kB$', re.MULTILINE)
    sizes = size_pattern.findall(smaps_content)
    total_vss_kb = sum(int(size) for size in sizes)
    total_vss_mb = total_vss_kb / 1024
    return total_vss_mb


folder = os.path.basename(sys.argv[1])
Vss_list = []

for filename in os.listdir(folder):
    if filename.endswith('.log'):
        Vss_list.append(GetAllVss(folder,filename))
        # ConvertToJson(foler, filename)
print(Vss_list)

