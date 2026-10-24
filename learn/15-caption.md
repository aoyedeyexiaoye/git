# 字幕、标题与会动的贴纸（笔记 15）

> 学习日期：2026-10-25 · 实测：给 16.1s 短片加标题 + 3 条段落字幕 + 浮动贴纸
> 输入 913 KB → 输出 **1096 KB**（多了约 180 KB）

## 一、三件事，三种表达式

| 需求 | 关键写法 |
|---|---|
| 只在某段时间显示 | `enable='between(t,0.6,4.0)'` |
| 文字淡入淡出 | `alpha='if(lt(t,0.6),t/0.6,if(lt(t,2.4),1,(3-t)/0.6))'` |
| 贴纸会动 | `overlay=x='W-w-24+10*sin(2*PI*t)':y='24+14*sin(2*PI*t/2)'` |

三者的共同点：**都能写含 `t` 的表达式**，这就是"时间轴动画"的全部秘密。

## 二、标题（居中 + 描边 + 淡入淡出）

```bash
drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':text='大白饭表情包':
  fontcolor=white:fontsize=56:borderw=3:bordercolor=black@0.65:
  x=(w-text_w)/2:y=h*0.12:
  alpha='if(lt(t,0.6),t/0.6,if(lt(t,2.4),1,(3-t)/0.6))':enable='between(t,0,3)'
```

- `borderw=3` 描边：白字压白底也能看清（本例底图就是白底，没描边会糊成一片）
- `x=(w-text_w)/2` 才是真居中，`x=w/2` 是"左边缘在中间"
- 淡入/淡出用**两段 if 拼**，比 `fade` 滤镜灵活得多（只作用于文字）

## 三、段落字幕（一条一段）

```bash
drawtext=...:'今天也在认真营业':y=h-96:enable='between(t,0.6,4.0)'
```

多条字幕就是链式多个 `drawtext`，**每条自己的 enable 决定何时出现**。

## 四、会动的贴纸（输入序号是最容易错的地方）

```bash
ffmpeg -i show.mp4 -i sticker.png -filter_complex "
  [1:v]scale=130:-1,format=rgba[st];
  [0:v][st]overlay=x='W-w-24+10*sin(2*PI*t)':y='24+14*sin(2*PI*t/2)'[v]
" -map "[v]" out.mp4
```

- 贴纸是**第 2 个输入**，所以是 `[1:v]`
- 加了贴纸后，`-map` 必须显式指向最后一级 `[v]`，否则输出的是原视频
- `format=rgba` 保留透明，否则贴纸带白底

四种运镜表达式（脚本里已封装）：

| 模式 | 表达式 | 效果 |
|---|---|---|
| none | `x=W-w-24:y=24` | 固定右上角 |
| **float** | `y='24+14*sin(2*PI*t/2)'` | 上下浮动 |
| slide | `x='W-w-24-(W)*max(0,(t-4)/2)'` | 4 秒后滑出画外 |
| spin | `x/y` 都用 sin/cos | 绕小圈 |

## 五、验证（抽帧看三处）

```bash
ffmpeg -ss 1.2 -i out.mp4 -vframes 1 c1.png    # 标题在不在
ffmpeg -ss 7   -i out.mp4 -vframes 1 c7.png    # 第 2 条字幕对不对
ffmpeg -ss 14  -i out.mp4 -vframes 1 c14.png   # 第 3 条字幕对不对
hstack 三张 → 一眼确认
```

实测：标题「大白饭表情包」+ 三条字幕（今天也在认真营业 / 偶尔摸鱼 / 但一直很可爱）+ 右上角浮动贴纸，全部正确。

## 六、踩坑

66. **文本转义**：`text='...'` 里的 `:` `,` `'` `%` 都要转义，中文文案里带逗号极常见 → 全换成 `\,` 之类
67. Windows 字体路径冒号要写成 `C\:/Windows/...`，否则被当成参数分隔
68. 白字压白底不描边 → 看不清；`borderw` + `bordercolor=black@0.6` 是标配
69. `-map` 忘了指向最后一级 → 加了半天字幕，输出还是原片
70. 音轨：`-c:a copy` 保留原音频；如果原片无音轨，别写 copy（会报错）

## 七、脚本用法

```bash
python captionize.py -i out/show.mp4 -o out/show_cap.mp4 \
  --title "大白饭表情包" \
  --caption "0.6,4.0,今天也在认真营业" \
  --caption "6.0,9.5,偶尔摸鱼" \
  --caption "12.0,15.5,但一直很可爱" \
  --sticker ../emoji/out/06_cheer.png --sticker-size 130 --sticker-motion float
```

## 八、产物

```
examples/slideshow/
├─ make_video.py        # 图片→短片（运镜/转场）
├─ captionize.py        # 加标题/字幕/浮动贴纸
└─ out/
   ├─ show.mp4          # 无字幕版
   ├─ show_cap.mp4      # 成片（带字幕与贴纸）
   └─ caption-check.png # 三处抽帧验证
```

## 下一步（明天）

- 主题⑯：给成片**配音**——ffmpeg 拼接 TTS 音频（本机若有 edge-tts/Piper 最好，否则先用音乐垫底）并做音量归一化 loudnorm
