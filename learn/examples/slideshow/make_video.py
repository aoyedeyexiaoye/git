#!/usr/bin/env python3
"""把一组图片做成带 Ken Burns 运镜 + 交叉转场的短片（纯 ffmpeg）。

用法：
    python make_video.py --indir ../emoji/out --out out/show.mp4 --clip 3 --transition 0.5
    python make_video.py --indir ... --out out/show.gif          # 按扩展名决定格式

原理（详见 learn/14-slideshow.md）：
- 每张图：zoompan 做缓慢推近（Ken Burns）→ 统一 fps/尺寸
- 段与段：xfade 交叉转场，offset 必须 = 已播时长 - 转场时长
- 输出 mp4 用 libx264 + yuv420p；gif 走两遍调色板
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

FFMPEG = os.environ.get("FFMPEG", r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe")


def build_filter(n: int, size: int, fps: int, clip: float, trans: float, zoom: bool) -> str:
    """返回 filter_complex 字符串。"""
    parts = []
    for i in range(n):
        # 每段：放大后 zoompan（避免黑边），再统一像素格式
        if zoom:
            parts.append(
                f"[{i}:v]scale={size * 2}:{size * 2}:force_original_aspect_ratio=increase,"
                f"crop={size * 2}:{size * 2},"
                f"zoompan=z='1+0.06*on/({fps}*{clip})':d=1:s={size}x{size}:fps={fps},"
                f"setsar=1,format=yuv420p[v{i}]"
            )
        else:
            parts.append(
                f"[{i}:v]scale={size}:{size}:force_original_aspect_ratio=decrease,"
                f"pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:white,setsar=1,format=yuv420p[v{i}]"
            )

    # 交叉转场链：第 k 段开始时，前面的总时长 = k*(clip-trans)
    prev = "v0"
    for k in range(1, n):
        offset = k * (clip - trans)
        out = f"x{k}"
        parts.append(
            f"[{prev}][v{k}]xfade=transition=fade:duration={trans}:offset={offset:.3f}[{out}]"
        )
        prev = out
    parts.append(f"[{prev}]format=yuv420p[vout]")
    return ";".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clip", type=float, default=3.0)
    ap.add_argument("--transition", type=float, default=0.5)
    ap.add_argument("--size", type=int, default=720)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--no-zoom", action="store_true", help="关掉 Ken Burns 运镜")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--exclude", default="", help="按子串排除文件名，多个用逗号分隔")
    a = ap.parse_args()

    imgs = sorted(p for p in Path(a.indir).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    for bad in [x.strip() for x in a.exclude.split(",") if x.strip()]:
        imgs = [p for p in imgs if bad not in p.name]
    if a.limit:
        imgs = imgs[: a.limit]
    if len(imgs) < 2:
        raise SystemExit(f"至少需要 2 张图，当前 {len(imgs)}")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fc = build_filter(len(imgs), a.size, a.fps, a.clip, a.transition, not a.no_zoom)

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for p in imgs:
        cmd += ["-loop", "1", "-t", str(a.clip), "-i", str(p)]
    cmd += ["-filter_complex", fc, "-map", "[vout]"]

    if out.suffix.lower() == ".gif":
        # GIF：先出中间 mp4，再两遍调色板
        tmp = out.with_suffix(".tmp.mp4")
        subprocess.run(cmd + ["-c:v", "libx264", "-crf", "18", str(tmp)], check=True,
                       creationflags=0x08000000)
        pal = out.with_suffix(".pal.png")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(tmp),
                        "-vf", "fps=12,scale=480:-1:flags=lanczos,palettegen", str(pal)],
                       check=True, creationflags=0x08000000)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(tmp), "-i", str(pal),
                        "-lavfi", "fps=12,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse", str(out)],
                       check=True, creationflags=0x08000000)
        tmp.unlink(missing_ok=True)
        pal.unlink(missing_ok=True)
    else:
        subprocess.run(cmd + ["-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(out)],
                       check=True, creationflags=0x08000000)

    dur = len(imgs) * a.clip - (len(imgs) - 1) * a.transition
    print(f"[ok] {out}  {out.stat().st_size // 1024} KB  ≈{dur:.1f}s  ({len(imgs)} 张 / 转场 {a.transition}s)")


if __name__ == "__main__":
    sys.exit(main())
