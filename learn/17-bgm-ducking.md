# 背景音乐与"人声闪避"（笔记 17）

> 学习日期：2026-10-25 · 实测：合成 BGM + sidechaincompress，闪避量 **17.1 dB**
> 成片：16.10s / 1210 KB / 48kHz 单声道

## 一、没有音乐素材也能有 BGM

ffmpeg 的 `lavfi` 可以现场合成。三个正弦叠成三和弦 pad：

```bash
ffmpeg -f lavfi -t 16.1 -i "sine=frequency=220:sample_rate=48000" \
       -f lavfi -t 16.1 -i "sine=frequency=277.18:sample_rate=48000" \
       -f lavfi -t 16.1 -i "sine=frequency=329.63:sample_rate=48000" \
       -filter_complex "[0:a][1:a][2:a]amix=inputs=3:normalize=0,
                        tremolo=f=0.25:d=0.35,lowpass=f=1400,volume=0.22,
                        afade=t=in:st=0:d=1,afade=t=out:st=15.1:d=1" bgm.wav
```

- 220 / 277.18 / 329.63 Hz = A 大三和弦（A3 C#4 E4）
- `tremolo` 给一点呼吸感，`lowpass=1400` 去掉刺耳高频
- 音量压到 0.22，给后面的闪避留空间

**这不是为了替代真音乐**，而是为了"没有素材时也能把流程跑通"。

## 二、闪避（ducking）的核心：sidechaincompress

```bash
[1:a]volume=0.35[bg];                          # BGM
[bg][0:a]sidechaincompress=                    # ← BGM 被 0:a（人声）触发压缩
    threshold=0.03:ratio=8:attack=20:release=400:makeup=1[duck];
[0:a][duck]amix=inputs=2:normalize=0:dropout_transition=0,
    loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]
```

参数含义（实测调出来的）：

| 参数 | 值 | 作用 |
|---|---|---|
| `threshold` | 0.03 | 人声超过这个电平就开始压 BGM |
| `ratio` | 8 | 压缩比，越大压得越狠 |
| `attack` | 20 ms | 多快开始压（太快会"抽气"） |
| `release` | 400 ms | 人声停了多久恢复 |

## 三、验证方式：只导出被压的 BGM

不靠耳朵，直接把 `[duck]` 单独导出来量：

```bash
ffmpeg -i show_vo.mp4 -f lavfi -t 16.1 -i "sine=frequency=220:..." \
  -filter_complex "[1:a]volume=0.35[bg];[bg][0:a]sidechaincompress=...[duck]" \
  -map "[duck]" _duck.wav
```

分段测音量（`-ss` 定位 + `volumedetect`）：

| 时段 | 有无人声 | BGM 电平 |
|---|---|---|
| 1.0~1.8s | 有 | **-47.3 dB** |
| 4.5~5.3s | 无 | **-30.2 dB** |

→ **闪避量 17.1 dB**，正是"说话时音乐自动退到背景"的效果，数字可复现。

## 四、踩坑（本轮三个都是采样率/长度的坑）

71. `loudnorm` 内部把采样率升到 **192kHz**，`aresample` 必须写在它**之后**；写前面没用（我第一次就写反了，输出还是 96kHz）
72. `amix` 默认 `normalize=1` 会把音量均分，人声直接被压低 → 必须 `normalize=0`
73. `sidechaincompress` 的 `makeup=1` 表示不额外增益；想要更明显的效果可适当加大，但会牺牲"自然感"
74. 合成 BGM 的时长必须 ≥ 视频时长，否则 `-shortest` 会把片子截短（上一轮踩过同类坑）

## 五、整条流水线（目前）

```
SD 出图 → make_video.py（运镜+转场）→ captionize.py（字幕/贴纸）
        → voiceover.ps1（SAPI 配音）→ bgm_mix.py（BGM+闪避）→ 成片
```

四五条命令，全程命令行，不需要任何剪辑软件。

## 六、产物

```
examples/slideshow/
├─ make_video.py      # 图片 → 短片
├─ captionize.py      # 标题/字幕/浮动贴纸
├─ voiceover.ps1      # 离线配音
├─ bgm_mix.py         # BGM 合成 + 闪避
└─ out/
   ├─ show.mp4        # 静默版
   ├─ show_cap.mp4    # 字幕版
   ├─ show_vo.mp4     # 配音版
   └─ show_final.mp4  # 成片（本轮）
```

## 下一步（明天）

- 主题⑱：把这条 4 步流水线收进**一个入口脚本**（`make_all.py`），一条命令出成片，并复用第 10 轮的幂等 + manifest 设计
