#!/usr/bin/env python3
"""给配音成片垫背景音乐，并用 sidechaincompress 做"人声闪避"（说话时 BGM 自动压低）。

用法：
    python bgm_mix.py -i out/show_vo.mp4 -o out/show_final.mp4
    python bgm_mix.py -i in.mp4 -o out.mp4 --bgm out/bgm.wav   # 用自己的音乐

设计（见 learn/17-bgm-ducking.md）：
- 没有现成音乐时，用 ffmpeg lavfi 合成一段三和弦 pad（220/277/330Hz）
- sidechaincompress：把配音当"触发信号"，BGM 在有人声时被压缩
- 最后 amix 时给 BGM 留 -18dB 左右的底，人声不抢戏
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

FFMPEG = os.environ.get("FFMPEG", r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe")


def run(args: list[str]) -> str:
    p = subprocess.run([FFMPEG, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=0x08000000)
    return (p.stdout or "") + (p.stderr or "")


def duration_of(path: Path) -> float:
    out = run(["-hide_banner", "-i", str(path)])
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        raise SystemExit("读不出时长")
    h, mnt, sec = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + sec


def make_bgm(dst: Path, secs: float, fade: float = 1.0) -> None:
    """合成一段柔和的 pad：三个正弦叠一起 + 低通 + 颤音 + 首尾淡入淡出。"""
    fc = (
        "[0:a][1:a][2:a]amix=inputs=3:normalize=0,"
        "tremolo=f=0.25:d=0.35,"
        "lowpass=f=1400,"
        f"volume=0.22,"
        f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0, secs - fade):.2f}:d={fade}"
    )
    p = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-t", str(secs), "-i", "sine=frequency=220:sample_rate=48000",
         "-f", "lavfi", "-t", str(secs), "-i", "sine=frequency=277.18:sample_rate=48000",
         "-f", "lavfi", "-t", str(secs), "-i", "sine=frequency=329.63:sample_rate=48000",
         "-filter_complex", fc, "-c:a", "pcm_s16le", str(dst)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=0x08000000,
    )
    if p.returncode != 0:
        raise SystemExit("BGM 合成失败：" + (p.stderr or "")[-500:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="带配音的视频")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--bgm", default="", help="自定义 BGM 音频；留空则自动合成")
    ap.add_argument("--bgm-vol", type=float, default=0.35, help="BGM 基础音量（0~1）")
    ap.add_argument("--threshold", type=float, default=0.03, help="闪避触发阈值")
    ap.add_argument("--ratio", type=float, default=8, help="压缩比（越大压得越狠）")
    ap.add_argument("--attack", type=int, default=20)
    ap.add_argument("--release", type=int, default=400)
    a = ap.parse_args()

    src = Path(a.input)
    if not src.exists():
        raise SystemExit(f"输入不存在：{src}")
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    secs = duration_of(src)
    bgm = Path(a.bgm) if a.bgm else out.parent / "_bgm.wav"
    if not a.bgm:
        print(f"[bgm] 合成 {secs:.2f}s 三和弦 pad -> {bgm}")
        make_bgm(bgm, secs)

    # [0] = 视频（含人声）, [1] = BGM
    fc = (
        f"[1:a]volume={a.bgm_vol}[bg];"
        # 用 [0:a] 作 sidechain key：有人声时压 BGM
        f"[bg][0:a]sidechaincompress=threshold={a.threshold}:ratio={a.ratio}:"
        f"attack={a.attack}:release={a.release}:makeup=1[duck];"
        f"[0:a][duck]amix=inputs=2:normalize=0:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"
    )
    p = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-i", str(bgm),
         "-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=0x08000000,
    )
    if p.returncode != 0:
        print((p.stderr or "")[-900:])
        raise SystemExit("合流失败")

    if not a.bgm:
        bgm.unlink(missing_ok=True)
    print(f"[ok] {out}  {out.stat().st_size // 1024} KB  {duration_of(out):.2f}s")


if __name__ == "__main__":
    sys.exit(main())
