# 给视频配音（笔记本 16）

> 学习日期：2026-10-25 · 实测：Windows 自带语音离线合成，3 句台词精确对位
> 结果：16.10s 原片 → 带配音 16.10s，1044 KB（视频流 copy，未重编码）

## 一、不用联网、不用装 TTS 引擎

Windows 自带 SAPI 就有中文语音：

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name + ' ' + $_.VoiceInfo.Culture }
```

本机可用：
- **Microsoft Huihui Desktop**（zh-CN，女声）← 用它
- Microsoft Zira Desktop（en-US）

合成一句到文件：

```powershell
$s.SelectVoice('Microsoft Huihui Desktop')
$s.Rate = 0            # -10~10 语速
$s.Volume = 90
$s.SetOutputToWaveFile('line01.wav')
$s.Speak('今天也在认真营业')
```

## 二、拼装流程（这是核心）

```
每句文本 → wav（SAPI）
   ↓ adelay 按起始秒摆放（毫秒）
   ↓ amix 混合（normalize=0，别让它自动压低音量）
   ↓ apad 补静音（让音频比视频长）→ -shortest 在片尾截断
   ↓ loudnorm 归一化到 -16 LUFS
   ↓ 与视频合流：-c:v copy（视频不重编码）
```

实测输出：
- 时长 **16.10s**（与原片完全一致）
- 音轨 **48kHz 单声道 aac**
- 响度 **mean -21.8 dB / max -1.5 dB**（loudnorm 的 TP=-1.5 生效）

## 三、验证方法：静音检测

不用听也能确认对位准确：

```bash
ffmpeg -i out.mp4 -af "silencedetect=n=-40dB:d=0.4" -f null -
```

实测（有声音的区间）：
```
0.73 ~ 2.51s    ← 第 1 句（设定在 0.6s）
6.13 ~ 6.95s    ← 第 2 句前半（设定在 6.0s）
7.42 ~ 8.61s    ← 第 2 句后半（中间有停顿）
12.14 ~ 13.48s  ← 第 3 句（设定在 12.0s）
```

三句全部落在指定时间附近（SAPI 起音有 ~0.1-0.7s 延迟，属正常）。

## 四、四个坑（这轮全踩了）

| 现象 | 原因 | 解法 |
|---|---|---|
| 输出被截短到 14.8s | 音频比视频短 + `-shortest` | 先 `apad=pad_dur=3` 让音频更长 |
| ffmpeg 永不结束 | `apad` 无上限 + 没有 `-shortest` | 两个必须配对使用 |
| 音轨 96000 Hz 单声道 | amix 后的默认重采样 | 末尾 `aresample=48000` |
| 中文脚本语法报错 | `.ps1` 无 BOM，PS5.1 按 ANSI 读 | 保存为 UTF-8 with BOM |

## 五、音画对的逻辑

关键只有一句：**延迟量 = 字幕起始秒 × 1000（毫秒）**。

```powershell
$ms = [int]($line.Start * 1000)
"[{0}:a]adelay={1}|{1}[a{0}]" -f ($k + 1), $ms
```

`adelay=1200|1200` 的写法是「左声道|右声道」，单声道素材写两遍即可。

## 六、还能再往上做

- **背景音乐 + 闪避**：`sidechaincompress` 让音乐在人声出现时自动压低
- **逐句字幕对齐**：`silencedetect` 的输出可以直接反推每条字幕该出现在哪
- **多角色**：不同句子用不同 Voice，做对话

## 七、产物

```
examples/slideshow/
├─ voiceover.ps1        # 台词表 → 配音 → 合流
└─ out/
   ├─ show.mp4          # 无声版
   ├─ show_cap.mp4      # 字幕版
   ├─ show_vo.mp4       # 配音版（本轮）
   └─ lines.txt         # 台词表（起始秒|文本）
```

## 下一步（明天）

- 主题⑰：背景音乐 + sidechaincompress 闪避（人声出现时自动压低 BGM），并合成最终成片
