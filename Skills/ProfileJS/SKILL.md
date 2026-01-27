---

name: profilejs
description: 当我给你一个js profile文件（.cpuprofile文件）并且让你根据这个profile获得信息的时候，使用这个skill。你需要用profile_js.py脚本来获取这个profile文件里关于函数耗时的详细信息，结合代码完成我的优化要求。

---

#### 工具

在Scripts文件夹下有个profile_js.py脚本，有两个功能，怎么用看下面：

- **Search**: `python profile_js.py <profile_file> search --func "<name>" [--hint "<file_hint>"]`
- **Inspect**: `python profile_js.py <profile_file> inspect --id <node_id>`

#### 流程

比如我会说“minimap的OnUpdate函数耗时有点高，看看有什么优化办法”。你要：

* **定位 (搜索与过滤)**：使用关键词运行 `search` 命令，--func后面跟的是函数名，这里是OnUpdate，--hint后面跟的是文件名的关键字，这里就是minimap，示例：`python profile_js.py <profile_file> search --func OpUpdate --hint minimap`。这会返回一个json数组：


```
 [{
    "node_id": 31,
    "function": "OnUpdate",
    "file_path": "file:///D:/P4/client/Content/JavaScript/product/ui/map/ui_minimap_wrapper.js",
    "line": 0,
    "stats": {
      "self_ms": 6.78,
      "total_ms": 180.02
    }
  },...]
```

当有多个返回的时候，你可以停下来问我要哪个，或者自己判断下，先深挖最多的那个。

* **深挖 (检查与追踪)**：对目标 `node_id` 运行 `inspect` 命令，id就是前面search返回的node_id，示例：`python profile_js.py <profile_file> inspect --id 34`。会返回给你一个breakdown，是这个函数的子函数耗时分布情况:

```
"breakdown": [
    {
      "function": "UpdateMonsterPoi",
      "node_id": 35,
      "total_ms": 64.49,
      "file_path": "file:///D:/P4/client/Content/JavaScript/product/ui/map/ui_minimap_wrapper.js",
      "percent": "35.8%"
    },
```

然后你可以根据这个数据，去读ts源码进行分析，有必要的话就用新的node_id继续inspect，直到breakdown为空，或者你觉得信息足够指导你优化了。基本就是和根据火焰图进行profile的情况一样，一层一层挖，看看有什么可以优化的地方。



#### 注意

* **JS to TS Mapping**: 注意火焰图里的文件路径是js的，一般在Content\JavaScript下面，真正的ts源文件，也就是你该参考的文件，在TsProj/下面
* **Ignore Wrappers**: 当你发现profile数据里的函数是game_profile.js 里的 `o.value`  时候，这只是装饰器模式的一个函数名，直接看其子函数即可。