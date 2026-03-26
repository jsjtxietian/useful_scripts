---
name: unreal-insights-frame-callees
description: 当我给你一个 unreal insights 的 `.utrace` 文件，并希望围绕某一帧或某个时间窗里的某个函数分析耗时、下钻子函数、定位热点时，使用这个 skill。你需要调用 `read_utrace.py`，拿到一个紧凑的聚合调用树，再结合代码完成分析和优化建议。
---

# Unreal Insights Frame Callees Skill

当用户给出一个 `.utrace` 文件，并希望分析某个函数在某一帧或某个时间窗里的耗时构成时，使用这个 skill。这个 skill 复用了 Unreal 现有工具链，拿到一个适合 agent 消化的极简结果。



## Example

如果用户明确告知了帧号或者起始时间，则直接选下列模式之一，否则按utrace大小建议用户告知二者之一：

* 按帧分析：

```bash
python "D:\P4\client\.codex\skills\ReadUtrace\scripts\read_utrace.py" --utrace "C:\Users\YX\AppData\Local\UnrealEngine\Common\UnrealTrace\Store\001\20260324_173015.utrace" --frame 85 --timer "ABaseMagicSky::Tick" --threads "GameThread" --verbose
```

* 按时间窗分析，会跳过 `TraceAnalyzer.exe`，适合大文件：

```bash
python "D:\P4\client\.codex\skills\ReadUtrace\scripts\read_utrace.py" --utrace "C:\Users\YX\AppData\Local\UnrealEngine\Common\UnrealTrace\Store\001\oppo_run_2.utrace" --start-time-ms 47619 --duration-ms 30 --timer "ABaseMagicSky::Tick" --threads "GameThread" --verbose
```

注意如果用户给的是类似 “47s 619ms” 这样的时间，需要换算成 `47619` 毫秒再传入。如果用户没有给 `--end-time-ms`，脚本会按下面的规则计算：

```text
end_time_ms = start_time_ms + duration_ms
```

默认 `duration_ms` 是 `30.0`。

`threads` 一般传 `GameThread`，除非用户明确了其他要求



## 输出格式

脚本输出一个极简 JSON：

- `frame`：如果走 `frame` 模式，`frame` 是具体帧号，如果走时间窗模式，`frame` 会是 `null`

- `timer`
- `tree`

其中：

- `total_time_ms`：当前聚合节点的包含时间

- `self_time_ms`：当前聚合节点自身耗时，不包含子节点
- `count`：当前时间窗内该聚合节点累计出现的次数
- `children`：该聚合节点下继续按调用关系聚合后的子节点



## 其他说明

这个结果是“某个时间窗内、某个 timer 的聚合子树”。

- 保留父子层级

- 保留总耗时、自耗时、调用次数

- 但不保留每一次具体调用实例的独立节点

所以它适合回答：

- 这个函数的主要耗时落在哪些子函数上
- 哪些分支最重
- 哪些节点调用次数高但单次耗时低

