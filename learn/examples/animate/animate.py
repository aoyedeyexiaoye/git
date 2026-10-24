#!/usr/bin/env python3
"""把一张静态贴纸做成动图：呼吸/弹跳/淡入淡出/GIF/插帧。

用法：
    python animate.py breathe -i sticker.png -o out/breathe.mp4
    python animate.py bounce  -i sticker.png -o out/bounce.gif
    python animate.py fade    -i sticker.png -o out/fade.mp4
    python animate.py interp  -i out/breathe.mp4 -o out/interp60.mp4

要点（详见 learn/09-animate.md）：
- 静态图做动画必须 `-loop 1 -t 时长 -r 30`，否则只有 1 帧
- zoompan 的 `d` 是"每张输入生成多少帧"，配 fps 用
- GIF 走两遍（palettegen → paletteuse），直接转会又大又脏
- minterpolate 补帧很吃 CPU，短片段用
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_FFMPEG = r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe"


def ffmpeg_bin() -> str:
    return os.environ.get("FFMPEG") or DEFAULT_FFMPEG


def run(args: list[str]) -> None:
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", *args]
    print("[run]", " ".join(args[:6]), "...")
    p = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if p.returncode != 0:
        print(p.stderr[-800:])
        raise SystemExit(f"ffmpeg 失败（exit {p.returncode}）")


def base_clip(src: Path, dst: Path, secs: float, size: int) -> None:
    """静态图 → 视频（必须 -loop 1，否则只出一帧）"""
    run([
        "-loop", "1", "-i", str(src), "-t", str(secs), "-r", "30",
        "-vf", f"scale={size}:{size}:force_original_aspect_ratio=decrease,"
               f"pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:white",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "18", str(dst),
    ])


def breathe(src: Path, dst: Path, size: int = 384, secs: float = 3) -> None:
    """呼吸感：zoompan 做缓慢放大缩小。"""
    run([
        "-loop", "1", "-i", str(src), "-t", str(secs), "-r", "30",
        "-vf", (
            f"scale={size * 2}:{size * 2},"
            f"zoompan=z='1.0+0.03*sin(2*PI*on/45)':d=1:s={size}x{size}:fps=30,"
            "format=yuv420p"
        ),
        "-c:v", "libx264", "-crf", "18", str(dst),
    ])


def fade(src: Path, dst: Path, size: int = 384, secs: float = 3) -> None:
    """淡入 + 淡出。"""
    run([
        "-loop", "1", "-i", str(src), "-t", str(secs), "-r", "30",
        "-vf", (
            f"scale={size}:{size}:force_original_aspect_ratio=decrease,"
            f"pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:white,"
            f"fade=t=in:st=0:d={secs / 3:.2f},fade=t=out:st={secs * 2 / 3:.2f}:d={secs / 3:.2f}"
        ),
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "18", str(dst),
    ])


def bounce(src: Path, dst: Path, size: int = 384, secs: float = 2) -> None:
    """弹跳：白色底 + 贴纸按 sin 上下移动。"""
    h = size + 80
    run([
        "-f", "lavfi", "-i", f"color=c=white:s={size}x{h}:d={secs}:r=30",
        "-loop", "1", "-i", str(src), "-t", str(secs),
        "-filter_complex",
        (
            f"[1:v]scale={size}:{size}:force_original_aspect_ratio=decrease,"
            f"format=rgba[fg];"
            f"[0:v][fg]overlay=x=0:y='20+18*abs(sin(2*PI*t))*1.2':format=auto,"
            "format=yuv420p[v]"
        ),
        "-map", "[v]", "-c:v", "libx264", "-crf", "18", str(dst),
    ])


def gif(src: Path, dst: Path) -> None:
    """GIF 两遍法：先生成调色板，再套用（体积小、颜色准）。"""
    pal = dst.with_suffix(".palette.png")
    run(["-i", str(src), "-vf", "fps=15,scale=320:-1:flags=lanczos,palettegen", str(pal)])
    run([
        "-i", str(src), "-i", str(pal),
        "-lavfi", "fps=15,scale=320:-1:flags=lanczos[x];[x][1:v]paletteuse",
        str(dst),
    ])
    pal.unlink(missing_ok=True)


def interp(src: Path, dst: Path, fps: int = 60) -> None:
    """光流补帧（很吃 CPU，短片段用）。"""
    run(["-i", str(src), "-vf", f"minterpolate=fps={fps}:mi_mode=mci", "-c:v", "libx264",
         "-crf", "18", str(dst)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["base", "breathe", "fade", "bounce", "gif", "interp"])
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--size", type=int, default=384)
    ap.add_argument("--secs", type=float, default=3)
    a = ap.parse_args()

    src, dst = Path(a.input), Path(a.output)
    if not src.exists():
        raise SystemExit(f"输入不存在：{src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    match a.action:
        case "base":
            base_clip(src, dst, a.secs, a.size)
        case "breathe":
            breathe(src, dst, a.size, a.secs)
        case "fade":
            fade(src, dst, a.size, a.secs)
        case "bounce":
            bounce(src, dst, a.size, a.secs)
        case "gif":
            gif(src, dst)
        case "interp":
            interp(src, dst)
    size_kb = dst.stat().st_size / 1024
    print(f"[ok] {dst} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
