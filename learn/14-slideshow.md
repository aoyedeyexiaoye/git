# 图片 → 短片：运镜与交叉转场（笔记 14）

> 学习日期：2026-10-25 · 实测：8 张表情图 → 720p 短片，16.1 秒 / 912 KB
> 目标：不装剪辑软件，用 ffmpeg 把一组静态图做成有运镜、有转场的短片

## 一、整体思路

```
8 张 PNG
  ↓ 每张：zoompan 缓慢推近（Ken Burns）
  ↓ 段间：xfade 交叉淡化
输出 MP4（720×720 / 30fps / h264 / yuv420p）
```

一条命令：

```bash
python make_video.py --indir ../emoji/out --out out/show.mp4 \
    --clip 2.5 --transition 0.5 --size 720 --exclude 00_all
```

## 二、filter 链的关键：offset 数学

```text
[fade 链] 第 k 段淡入开始时间 = k × (clip − transition)
```

8 张、每段 2.5s、转场 0.5s：
- 第 1 次转场在 **2.0s**
- 第 2 次在 **4.0s**
- …总长 = 8×2.5 − 7×0.5 = **16.5s**（实测 16.10s，差在末帧与 fps 对齐）

**offset 写错是这类片子最常见的翻车**：写成 `k × clip` 会导致转场时刻越来越偏，最后一段直接黑屏。

## 三、Ken Burns 运镜（zoompan）

```text
scale=1440:1440:force_original_aspect_ratio=increase,
crop=1440:1440,
zoompan=z='1+0.06*on/(fps*clip)':d=1:s=720x720:fps=30
```

- 先放大 2 倍再裁，**避免推近时露出黑边**
- `z` 用 `on`（当前帧序号）做线性增长，整段从 1.0 推到 1.06
- `d=1` + `fps=30`：逐帧推进

## 四、验证方法（别看时长就完事）

时长对不代表内容对。抽 4 个时间点拼图：

```bash
for t in 1 5 9 14; do ffmpeg -ss $t -i show.mp4 -vframes 1 p$t.png; done
ffmpeg -i p1.png -i p5.png -i p9.png -i p14.png -filter_complex "...hstack=inputs=4" check.png
```

实测 1s / 5s / 9s / 14s 分别是 4 个不同角色 → 说明**转场链真的在推进**，不是卡在第一张。

## 五、踩坑

61. 目录里混进拼版图（`00_all.png`）→ 每轮多一张，且顺序被打乱；加 `--exclude` 过滤
62. `xfade` 前各段**必须统一 fps / 分辨率 / SAR**，否则转场瞬间跳帧或拉伸（`setsar=1` 别省）
63. `zoompan` 不先放大裁切 → 推近时四周露黑边
64. 输出忘 `-pix_fmt yuv420p` → 微信/部分播放器黑屏
65. 转场时长 ≥ 单段时长 → 负 offset，直接报错或画面坍塌

## 六、参数速查（720p，8 图）

| 想要 | clip | transition | 总长 |
|---|---|---|---|
| 快节奏 | 1.5 | 0.3 | ≈10.4s |
| 常规 | 2.5 | 0.5 | ≈16.5s |
| 慢慢看 | 4.0 | 0.8 | ≈26.4s |

体积参考：720p/30fps/16s ≈ **900 KB**；同长度 480p ≈ 400 KB。

## 七、产物

```
examples/slideshow/
├─ make_video.py           # 图片→短片（运镜/转场/GIF 三合一）
└─ out/
   ├─ show.mp4             # 8 张表情的短片
   └─ timeline-check.png   # 4 个时间点抽帧验证
```

## 下一步（明天）

- 主题⑮：给短片**加字幕/贴图**（drawtext 时间轴控制 + 贴纸 overlay 位置动画），做成"表情包宣传片"
