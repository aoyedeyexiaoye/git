# 让贴纸动起来（笔记 09）

> 学习日期：2026-10-25 · 全部命令本机实测（ffmpeg 7.1）
> 目标：静态 PNG → 呼吸 / 弹跳 / 淡入淡出 / GIF / 补帧，全部可批量

## 一、四个动作与实测体积（384px，3 秒）

| 动作 | 命令要点 | 产物 | 体积 |
|---|---|---|---|
| 呼吸 | `zoompan=z='1+0.03*sin(2*PI*on/45)'` | mp4 384×384 | **78 KB** |
| 淡入淡出 | `fade=t=in:st=0:d=1,fade=t=out:st=2:d=1` | mp4 | **58 KB** |
| 弹跳 | `overlay=y='20+18*abs(sin(2*PI*t))'` | mp4 | **36 KB** |
| 转 GIF | `fps=15,scale=320:-1` + palettegen/paletteuse | gif | **1796 KB** |
| 补帧 60fps | `minterpolate=fps=60:mi_mode=mci` | mp4 | 88 KB（耗时 **2.2s**） |

**最刺眼的一条**：同一个 2 秒动画，MP4 只要 36 KB，GIF 要 1796 KB —— **50 倍**。

## 二、静态图做动画的三条铁律

1. **必须 `-loop 1 -t 时长 -r 30`**：不 `-loop 1` 就只得到 1 帧（不是"不动"，是"没有时长"）
2. **`zoompan` 的 `d` 与 `fps` 配合**：`d` 是"每张输入画面生成多少帧"，配 `d=1+fps=30` 表示逐帧推进
3. **导出前 `format=yuv420p`**：否则部分播放器/微信不认高色深

## 三、GIF 必须走两遍（palettegen → paletteuse）

```bash
ffmpeg -i in.mp4 -vf "fps=15,scale=320:-1:flags=lanczos,palettegen" palette.png
ffmpeg -i in.mp4 -i palette.png \
       -lavfi "fps=15,scale=320:-1:flags=lanczos[x];[x][1:v]paletteuse" out.gif
```

直接转的 GIF 会又大又脏（颜色量化 256 色随机挑）。两遍法先统计真实用色再套用。

但**能不用 GIF 就别用**：微信/QQ 现在都支持 MP4 表情，体积差 50 倍。

## 四、弹跳的实现（白底 + overlay 位移）

```bash
ffmpeg -f lavfi -i "color=c=white:s=384x464:d=2:r=30" \
       -loop 1 -i sticker.png -t 2 \
       -filter_complex "[1:v]scale=384:384,format=rgba[fg];[0:v][fg]overlay=x=0:y='20+18*abs(sin(2*PI*t))'[v]" \
       -map "[v]" -c:v libx264 -crf 18 bounce.mp4
```

- 画布比贴纸高 80px，留出弹跳空间
- `y` 用 `abs(sin)` 而不是 `sin`：贴纸只会往上跳，不会掉到画布外
- `format=rgba` 保留透明，overlay 才能正确叠在白底上

## 五、验证动画是否真的动了（别只看文件大小）

抽两帧并排，一眼就能确认位移：

```bash
ffmpeg -ss 0.15 -i bounce.mp4 -vframes 1 f1.png
ffmpeg -ss 0.75 -i bounce.mp4 -vframes 1 f2.png
ffmpeg -i f1.png -i f2.png -filter_complex hstack=inputs=2 frames.png
```

实测：两帧里贴纸垂直位置明显不同（`bounce-frames.png`）。

## 六、补帧（minterpolate）值不值

- 3 秒 384px 片段：**2.2 秒**算完，可接受
- 但它假设画面连续运动；贴纸这种**硬边缘 + 大面积纯白**容易在边缘产生"果冻"抖纹
- 结论：**真人/实拍视频用它有明显收益；卡通贴纸没必要**，直接用 30fps 输出更稳

## 七、踩坑

36. 忘 `-loop 1` → 输出只有一帧，报错都没有，最坑
37. `palettegen` 不先 `fps/scale` → 调色板按原始分辨率统计，套用后颜色错位
38. `overlay` 的 `y` 用 `sin` 不加 `abs` → 一半时间贴纸跑到画布外
39. MP4 默认 `yuv444p` 在部分播放器变绿/黑屏 → 显式 `-pix_fmt yuv420p`
40. 中文路径传参：Python `subprocess` 用列表参数（不经 shell）最稳，别拼字符串

## 八、产物

```
examples/animate/
├─ animate.py            # base/breathe/fade/bounce/gif/interp 六个动作
└─ out/
   ├─ bounce.mp4         # 36 KB 弹跳示例
   └─ bounce-frames.png  # 两帧对比（验证真的动了）
```

## 下一步（明天）

- 主题⑩：把 SD 出图 + ffmpeg 串成**一条流水线**（出 8 张表情 → 自动动起来 → 拼成一张预览 GIF），并加失败重试
