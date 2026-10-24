# ffmpeg 视频剪辑实战（笔记 04）

> 学习日期：2026-10-25 · 全部命令在本机**实际跑通**（ffmpeg 7.1 essentials build）
> 目标：不用任何剪辑软件，用命令行完成裁切/拼接/变速/字幕/转格式

## 零、先有 ffmpeg（不用管理员）

```powershell
# 拿官方构建的 ffmpeg.exe（31MB），装到当前 Python 的 site-packages
& E:\AI\Deepseek1\py310\python.exe -m pip install imageio-ffmpeg `
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple
# 找到二进制
& E:\AI\Deepseek1\py310\python.exe -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
```

本机结果：`ffmpeg version 7.1-essentials_build-www.gyan.dev`（已复制到 `E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe`）

## 一、七个核心命令（已实测）

```bash
# 1) 造测试片（无素材时自检用）
ffmpeg -y -f lavfi -i "testsrc=size=640x360:rate=30" -f lavfi -i "sine=frequency=440" \
       -t 3 -pix_fmt yuv420p -c:v libx264 -c:a aac 1_src.mp4

# 2) 裁切（-ss 在前 = 快速定位，-c copy 不重编码）
ffmpeg -y -ss 1 -i 1_src.mp4 -t 1 -c copy 2_trim.mp4

# 3) 变速（视频 setpts，音频 atempo，必须分开写再合并）
ffmpeg -y -i 1_src.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" \
       -map "[v]" -map "[a]" 3_speed2x.mp4

# 4) 拼接（先写 list.txt：file 'a.mp4'，再 concat）
ffmpeg -y -f concat -safe 0 -i list.txt -c copy 4_concat.mp4

# 5) 烧文字/字幕（Windows 字体路径的冒号要转义成 \:）
ffmpeg -y -i 1_src.mp4 -vf "drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':\
text='大白饭测试':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-80" -c:a copy 5_text.mp4

# 6) 缩放 + 裁剪（scale 宽度自动 -2 保证偶数，crop 居中裁 640x360）
ffmpeg -y -i 1_src.mp4 -vf "scale=1280:-2,crop=640:360" -an 6_scale_crop.mp4

# 7) 转 GIF（fps 与 scale 控制在前面，体积才小）
ffmpeg -y -i 1_src.mp4 -vf "fps=10,scale=320:-1:flags=lanczos" 7_a.gif

# 8) 抽某一帧
ffmpeg -y -i 1_src.mp4 -vf "select=eq(n\,30)" -vframes 1 8_frame.png
```

**验证结果**：8 个产物全部生成；第 5 条抽帧肉眼确认中文「大白饭测试」正确烧进画面（微软雅黑 msyh.ttc 可用）。

## 二、什么时候能 `-c copy`（快且无损），什么时候不行

| 操作 | 能否 copy | 原因 |
|---|---|---|
| 裁切片段 | ✅ | 只改容器时间轴（但起点会对齐到最近关键帧） |
| 拼接 | ✅ **仅当编码参数完全一致** | 分辨率/编码/profile 不同就必须 filter 重编码 |
| 变速 | ❌ | 每帧时间戳都变了 |
| 缩放/裁切画面 | ❌ | 像素内容变了 |
| 加字幕 | ❌ | 画面多了东西 |

**拼接不同参数时的正确做法**（统一成同一规格）：

```bash
ffmpeg -y -i a.mp4 -i b.mp4 -filter_complex \
"[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:-1:-1,setsar=1[v0]; \
 [1:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:-1:-1,setsar=1[v1]; \
 [v0][v1]concat=n=2:v=1:a=0[v]" -map "[v]" out.mp4
```

## 三、踩坑

14. `-ss` 放在 `-i` **前**是快速定位（不精确，可能偏几帧）；放**后**是逐帧解码（精确但慢）
15. 用 `-c copy` 裁切会从**最近的关键帧**开始，视频可能比要求的多几帧——要帧级精确就去掉 `-c copy`
16. 变速只写 `setpts` 不改音轨 → **音画不同步**；必须同时 `atempo`（范围 0.5~2.0，超出要串联多个）
17. Windows 上 drawtext 的字体路径：`C:/...` 里的冒号会被当成选项分隔，要写成 `C\:/...`
18. GIF 直接转会几百 MB；必须 `fps` + `scale` 双重压缩，需要更高质量再加 `split` + `palettegen`/`paletteuse`
19. 中文路径/中文参数在 PowerShell 里最容易乱码：命令写成 `.ps1` 文件并保存为 **UTF-8 with BOM** 再执行

## 四、常用组合菜单

| 想做的事 | 命令要点 |
|---|---|
| 压小体积 | `-c:v libx264 -crf 23 -preset medium`（crf 越大越小越糊，18~28） |
| 只留音频 | `-vn -c:a aac -b:a 128k out.m4a` |
| 提取音频转 mp3 | `-vn -c:a libmp3lame -q:a 2` |
| 加封面/元数据 | `-i cover.jpg -map 0 -map 1 -c copy -disposition:v:1 attached_pic` |
| 批量转码 | 外层 for 循环调同一条命令，别用 `-pattern_type glob` 在 Windows 上 |

## 五、现成脚本

`examples/ffmpeg/recipes.ps1`（**必须以 UTF-8 with BOM 保存**）已把上面 6 个动作封装成参数：

```powershell
.\recipes.ps1 -Action trim   -In a.mp4 -Out b.mp4 -Start 1 -Duration 3
.\recipes.ps1 -Action speed  -In a.mp4 -Out b.mp4 -Rate 2
.\recipes.ps1 -Action concat -In "a.mp4,b.mp4" -Out c.mp4
.\recipes.ps1 -Action text   -In a.mp4 -Out b.mp4 -Text "hello"
.\recipes.ps1 -Action gif    -In a.mp4 -Out b.gif
.\recipes.ps1 -Action frame  -In a.mp4 -Out b.png -At 1
```

脚本会自己找 ffmpeg：先看 `tools/ffmpeg/ffmpeg.exe`，没有就回退到 `imageio_ffmpeg` 提供的二进制。
6 个动作全部实测通过（trim / speed / concat / text / gif / frame）。

## 下一步（明天）

- 主题⑤：程序与自动化脚本——把这几天的 ffmpeg/SD 命令包成一个可复用 CLI（argparse + 配置），并加日志/失败重试
