#!/usr/bin/env python3
"""给短片加字幕/标题 + 会动的贴纸（drawtext 时间轴 + overlay 位置表达式）。

用法：
    python captionize.py -i out/show.mp4 -o out/show_cap.mp4 \
        --title "大白饭表情包" \
        --caption "0.5,3.2,开场" --caption "3.5,6.0,日常" \
        --sticker ../emoji/out/06_cheer.png --sticker-size 140

要点（见 learn/15-caption.md）：
- drawtext 的 enable='between(t,a,b)' 控制显示区间
- alpha 表达式做淡入淡出，比硬切舒服
- overlay 的 x/y 可以写含 t 的表达式 → 贴纸就会动
- Windows 字体路径的冒号必须转义：C\:/Windows/Fonts/msyh.ttc
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

FFMPEG = os.environ.get("FFMPEG", r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe")
FONT = r"C\:/Windows/Fonts/msyh.ttc"


def esc(text: str) -> str:
    """drawtext 文本转义：冒号、逗号、单引号、百分号都要处理。"""
    return (text.replace("\\", r"\\").replace(":", r"\:").replace(",", r"\,")
            .replace("'", r"\'").replace("%", r"\%"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--caption", action="append", default=[],
                    help="start,end,文本 —— 可重复多次")
    ap.add_argument("--sticker", default="")
    ap.add_argument("--sticker-size", type=int, default=140)
    ap.add_argument("--sticker-motion", choices=["none", "float", "slide", "spin"], default="float")
    a = ap.parse_args()

    if not Path(a.input).exists():
        raise SystemExit(f"输入不存在：{a.input}")

    inputs = ["-i", a.input]
    fc: list[str] = []
    cur = "0:v"

    # ① 标题：0~3s，淡入淡出
    if a.title:
        fc.append(
            f"[{cur}]drawtext=fontfile='{FONT}':text='{esc(a.title)}':"
            "fontcolor=white:fontsize=56:borderw=3:bordercolor=black@0.65:"
            "x=(w-text_w)/2:y=h*0.12:"
            "alpha='if(lt(t,0.6),t/0.6,if(lt(t,2.4),1,(3-t)/0.6))':enable='between(t,0,3)'[v1]"
        )
        cur = "v1"

    # ② 段落字幕：每条一段 between()
    for i, spec in enumerate(a.caption):
        parts = spec.split(",", 2)
        if len(parts) < 3:
            raise SystemExit(f"--caption 格式应为 start,end,文本：{spec}")
        st, en, text = parts[0].strip(), parts[1].strip(), parts[2]
        out = f"c{i+1}"
        fc.append(
            f"[{cur}]drawtext=fontfile='{FONT}':text='{esc(text)}':"
            "fontcolor=white:fontsize=40:borderw=3:bordercolor=black@0.7:"
            "x=(w-text_w)/2:y=h-96:"
            f"enable='between(t,{st},{en})'[{out}]"
        )
        cur = out

    # ③ 会动的贴纸
    if a.sticker:
        if not Path(a.sticker).exists():
            raise SystemExit(f"贴纸不存在：{a.sticker}")
        inputs += ["-i", a.sticker]
        sidx = len(inputs) // 2 - 1  # 输入序号：-i 计数
        motion = {
            "none": "x=W-w-24:y=24",
            "float": "x=W-w-24:y='24+14*sin(2*PI*t/2)'",
            "slide": "x='W-w-24-(W)*max(0,(t-4)/2)':y=24",
            "spin": "x='W-w-24+10*sin(2*PI*t)':y='24+10*cos(2*PI*t)'",
        }[a.sticker_motion]
        out = f"s{len(fc)}"
        fc.append(f"[{sidx}:v]scale={a.sticker_size}:-1,format=rgba[st]")
        fc.append(f"[{cur}][st]overlay={motion}:format=auto,format=yuv420p[{out}]")
        cur = out

    if fc:
        cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(fc), "-map", f"[{cur}]",
               "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy",
               a.output]
    else:
        cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs,
               "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", a.output]

    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=0x08000000)
    if p.returncode != 0:
        print(p.stderr[-900:])
        raise SystemExit(f"ffmpeg 失败（exit {p.returncode}）")

    out = Path(a.output)
    print(f"[ok] {out}  {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    sys.exit(main())
