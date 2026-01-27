import json
import argparse
import sys
import os

class ProfileAgent:
    def __init__(self, filepath):
        if not os.path.exists(filepath):
            print(json.dumps({"error": f"File not found: {filepath}"}))
            sys.exit(1)
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except Exception as e:
            print(json.dumps({"error": f"JSON decode error: {str(e)}"}))
            sys.exit(1)
            
        self.nodes = {n['id']: n for n in self.data['nodes']}
        self.samples = self.data['samples']
        self.time_deltas = self.data['timeDeltas']
        
        # 预计算
        self._init_data()

    def _init_data(self):
        # 1. 初始化字段
        for n in self.nodes.values():
            n['selfTime'] = 0
            n['totalTime'] = 0
            n['children_ids'] = n.get('children', [])
            n['parent_id'] = None

        # 2. 建立父子关系索引
        for nid, node in self.nodes.items():
            for cid in node['children_ids']:
                if cid in self.nodes:
                    self.nodes[cid]['parent_id'] = nid

        # 3. 计算 Self Time (累计 timeDeltas)
        # 确保 samples 和 timeDeltas 长度一致
        count = min(len(self.samples), len(self.time_deltas))
        for i in range(count):
            node_id = self.samples[i]
            delta = self.time_deltas[i]
            if node_id in self.nodes:
                self.nodes[node_id]['selfTime'] += delta

        # 4. 递归计算 Total Time
        # V8 的 root 通常是 nodes[0] 或 id=1
        root = self.nodes.get(1) or self.nodes[self.data['nodes'][0]['id']]
        self._calc_total(root['id'])

    def _calc_total(self, node_id):
        node = self.nodes[node_id]
        child_total = 0
        for cid in node['children_ids']:
            child_total += self._calc_total(cid)
        node['totalTime'] = node['selfTime'] + child_total
        return node['totalTime']

    def _fmt_ms(self, micro_sec):
        return round(micro_sec / 1000.0, 2)

    def search(self, func_name, file_hint=None):
        """
        模糊搜索函数，返回候选项列表
        """
        candidates = []
        func_lower = func_name.lower()
        hint_lower = file_hint.lower() if file_hint else None

        for nid, node in self.nodes.items():
            frame = node.get('callFrame', {})
            fname = frame.get('functionName', '') or "(anonymous)"
            url = frame.get('url', '')
            
            # 过滤1: 函数名
            if func_lower not in fname.lower():
                continue
            
            # 过滤2: 文件 Hint
            if hint_lower and hint_lower not in url.lower():
                continue

            # 过滤3: 忽略耗时极小的噪声 (比如 Total < 0.1ms)
            if node['totalTime'] < 100: 
                continue

            candidates.append({
                "node_id": nid,
                "function": fname,
                "file_path": url,
                "line": frame.get('lineNumber', 0),
                "stats": {
                    "self_ms": self._fmt_ms(node['selfTime']),
                    "total_ms": self._fmt_ms(node['totalTime'])
                }
            })
        
        # 按 Total Time 降序排列，AI 应该优先看耗时最长的
        candidates.sort(key=lambda x: x['stats']['total_ms'], reverse=True)
        return candidates[:5] # 只返回前5个最有嫌疑的

    def inspect(self, node_id):
        """
        精确查看某个节点的构成
        """
        if node_id not in self.nodes:
            return {"error": "Node ID not found"}
            
        node = self.nodes[node_id]
        frame = node.get('callFrame', {})
        
        # 1. 基础信息
        result = {
            "node_id": node_id,
            "function": frame.get('functionName', '(anonymous)'),
            "file_path": frame.get('url', ''),
            "line": frame.get('lineNumber', 0),
            "stats": {
                "self_ms": self._fmt_ms(node['selfTime']),
                "total_ms": self._fmt_ms(node['totalTime'])
            }
        }

        # 2. 调用来源 (Parent)
        pid = node.get('parent_id')
        if pid and pid in self.nodes:
            p_frame = self.nodes[pid].get('callFrame', {})
            result["called_by"] = {
                "function": p_frame.get('functionName', '(unknown)'),
                "node_id": pid
            }

        # 3. 耗时分布 (Children)
        children_list = []
        for cid in node['children_ids']:
            c = self.nodes[cid]
            c_total = c['totalTime']
            # 过滤掉占比极小的子函数 (<1% 或 <0.1ms) 减少干扰
            if c_total < 100: continue 
            
            children_list.append({
                "function": c.get('callFrame', {}).get('functionName', '(anonymous)'),
                "node_id": cid,
                "total_ms": self._fmt_ms(c_total),
                "file_path": c.get('callFrame', {}).get('url', '')
            })

        # 排序
        children_list.sort(key=lambda x: x['total_ms'], reverse=True)
        
        # 计算百分比
        total_time = node['totalTime']
        for child in children_list:
            if total_time > 0:
                percent = (child['total_ms'] / result['stats']['total_ms']) * 100
                child['percent'] = f"{percent:.1f}%"
            else:
                child['percent'] = "0%"

        result["breakdown"] = children_list[:10] # Top 10 子函数
        return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Path to .cpuprofile')
    subparsers = parser.add_subparsers(dest='cmd', required=True)
    
    # search 命令
    p_search = subparsers.add_parser('search')
    p_search.add_argument('--func', required=True)
    p_search.add_argument('--hint', default=None)
    
    # inspect 命令
    p_inspect = subparsers.add_parser('inspect')
    p_inspect.add_argument('--id', type=int, required=True)

    args = parser.parse_args()
    agent = ProfileAgent(args.file)

    if args.cmd == 'search':
        print(json.dumps(agent.search(args.func, args.hint), indent=2))
    elif args.cmd == 'inspect':
        print(json.dumps(agent.inspect(args.id), indent=2))