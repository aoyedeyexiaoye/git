# 一条命令出成片：把流水线收口（笔记 18）

> 学习日期：2026-10-25 · 实测：4 步全跑 5 秒左右，幂等重跑 **0.2 秒**
> 产物：`1_video ≈ 2_captions → 3_voice → 4_final`（16.10s / 1396 KB）

## 一、入口

```bash
python make_all.py --images ../emoji/out --project proj1 \
  --title "大白饭表情包" \
  --caption "0.6,4.0,今天也在认真营业" \
  --caption "6.0,9.5,偶尔摸鱼" \
  --caption "12.0,15.5,但一直很可爱" \
  --lines out/lines.txt --sticker ../emoji/out/06_cheer.png
```

四个步骤各自有独立产物，**中间产物全部保留**（方便只重做某一步）：

```
proj1/
├─ 1_video.mp4      912 KB   # 运镜 + 转场
├─ 2_captions.mp4  1096 KB   # 标题/字幕/浮动贴纸
├─ 3_voice.mp4     1228 KB   # SAPI 配音
├─ 4_final.mp4     1396 KB   # BGM + 闪避
└─ manifest.json
```

## 二、幂等设计的两个层次

| 判断 | 含义 |
|---|---|
| 产物比所有输入新 | **直接复用**（哪怕这次没跑过） |
| manifest 里有记录 | 说明是"自己产出的"，可追溯 |

实测：全量跑约 **5 秒**；原样再跑 **0.2 秒**（15~25×）。

`--only captions` 可以只重跑字幕；`--force` 强制全部重做。

## 三、这轮踩到的真问题：SAPI 的进程链限制

**现象**：`voiceover.ps1` 直接跑正常；但由 `make_all.py`（Python）→ `powershell` 调用时，`SelectVoice` 报
`No voice installed on the system or none available with the current security setting`。

排查过程（值得记下来）：
1. 同一台机器、同一脚本，直接调用 ✅ / Python 子进程调用 ❌
2. 从 Python 里枚举语音 `GetInstalledVoices()` → **能列出 Huihui**（说明不是"没装"）
3. 但只要 `SelectVoice` 就失败 → 是**安全上下文**问题，不是缺语音
4. 加不加 `CREATE_NO_WINDOW` 都一样

**结论**：这是环境限制（孙进程拿不到语音合成权限），不是代码 bug。

**工程上的处理**（比硬刚环境更值）：
- 保留 `voiceover.ps1` 可独立运行（在普通 PowerShell 里跑就正常）
- `make_all.py` 检测到 `3_voice.mp4` 已存在且比输入新时**直接复用**，不再重复调用
- 于是"配音"这一步变成"可以先手工跑一次，之后流水线自动接管"

## 四、踩坑

75. 流水线里嵌交互式/系统级组件（TTS、GUI）时，**进程层级会改变可用权限**——同级跑通不代表孙进程跑通
76. 幂等判断只看 manifest 会漏掉"别人/别的步骤产出的文件"；**产物 mtime 比 manifest 更可靠**
77. 已知缺陷：**被复用的步骤不会写进 manifest**（本例 `voice` 就没记录）→ 想要完整审计，需要在 skip 分支里补一条 `adopted: true`
78. 中间产物一定要分文件名（`1_`/`2_`/`3_`/`4_`），否则排查时根本分不清坏在哪一步

## 五、现在这套东西能干什么

```
素材图片 ──┐
           ├─→ 运镜短片 ─→ 字幕贴纸 ─→ 配音 ─→ BGM闪避 ─→ 成片
SD 出图 ───┘      (make_video)  (captionize)  (voiceover)  (bgm_mix)
                        ↑ 全部由 make_all.py 串起来
```

换素材只要换 `--images` 目录；换文案只改 `--caption`。

## 六、产物

```
learn/
├─ 18-make-all.md
└─ examples/slideshow/
   ├─ make_all.py               # 统一入口（幂等 + manifest）
   ├─ make_video.py / captionize.py / bgm_mix.py / voiceover.ps1
   └─ proj1/                    # 一次完整运行的四个中间产物 + 成片
```

## 下一步（明天）

- 主题⑲：把 `learn/` 里的 18 篇笔记做成**静态站点**（目录/搜索/代码高亮），顺便验证一下 Markdown 渲染细节
