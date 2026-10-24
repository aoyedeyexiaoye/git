# 一条流水线：出图 → 动起来 → 拼预览（笔记 10）

> 学习日期：2026-10-25 · 本机实测（SD 127.0.0.1:7860 + ffmpeg 7.1）
> 目标：把前 9 天的零散命令串成**一条命令跑完**的流水线，并且能重跑、能续跑、不炸

## 一、一条命令

```bash
python pipeline.py --outdir run1 --emotions 4 --size 320 --steps 18 --animate bounce
```

跑完得到：

```
run1/
├─ 01_happy.png  01_happy.mp4     # 4 个情绪，各一张静图 + 一个弹跳动画
├─ 02_deadpan.png ...
├─ preview.png                     # 4×1 预览拼图
└─ manifest.json                   # 每一步的状态记录
```

## 二、实测数字（这是本轮最有价值的部分）

| 指标 | 结果 |
|---|---|
| 首次全流程（4 图 + 4 动画 + 拼图） | **138.2 秒** |
| **原样再跑一次**（幂等跳过） | **0.4 秒** |
| 提速倍率 | **约 345×** |
| 失败数 | 0 |

也就是说：**幂等设计不是洁癖，是实打实省时间**——调参数时你只会重跑变的那一步。

## 三、三个必须有的设计

### 1. 幂等（跳过已完成）

```python
if entry.get("image") and png.exists():
    print("图片已存在，跳过")
else:
    ...生成...
```

产物文件 + manifest 双条件判断：只看文件会误判（半截文件），只看 manifest 会漏掉被手动删掉的文件。

### 2. 重试（单步失败不拖垮整批）

```python
def retry(fn, tries=3, delay=2.0, what=""):
    for i in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:
            print(f"! {what} 第 {i}/{tries} 次失败：{e}")
            if i < tries: time.sleep(delay * i)   # 递增退避
    raise RuntimeError(f"{what} 重试耗尽")
```

`retry()` 把「SD 请求」和「ffmpeg 调用」都包起来——两类失败原因完全不同（网络 / 编码），但都需要重试。

### 3. manifest 记录每一步

```json
{
  "items": {
    "happy": {
      "image": {"path": "01_happy.png", "bytes": 101517},
      "video": {"path": "01_happy.mp4", "bytes": 29486}
    }
  }
}
```

- 成功记 path/bytes，失败记 `{"error": "..."}`，**失败也写入**，下次能看出哪步坏了
- 每完成一个子步骤就落盘一次（`save_manifest`），中途 Ctrl+C 不丢进度

## 四、失败隔离

外层 try 包住单个情绪：某一张崩了 → 记 error → `continue` 到下一张，最后统一汇报：

```
=== 汇总 ===
成功 3 / 共 4；失败 1：cry
```

并 `raise SystemExit(1)` 让调用方能按退出码判断。

## 五、踩坑

41. `lambda` 里写 `retry(...)` 忘了捕获外层变量 → 闭包晚绑定，重试时用的还是最后一次的值；本例用默认参数写法规避
42. manifest 不记录「失败」→ 下次续跑会以为「没做过」，无限重试同一张坏图
43. 只按文件存在判断已完成 → 上次中断留下半截 PNG，会被当成成功
44. 预览拼图那一行也要包 `retry`：PIL 打开损坏 PNG 会抛异常，不该让整批功亏一篑
45. 批量时**单张尺寸别贪大**：320px 出图约 12 秒/张，512px 约 20 秒/张，8 张差一分钟

## 六、产物

```
examples/pipeline/
├─ pipeline.py       # 出图 + 动画 + 拼图 + manifest + 重试
└─ run1/
   ├─ preview.png    # 4 情绪预览
   └─ manifest.json  # 状态清单
```

## 下一步（明天）

- 主题⑪：回到插件线——把这条流水线包成 **DSH 插件工具**（`ctx.tools.register`），这样在聊天里一句话就能出整套表情包
