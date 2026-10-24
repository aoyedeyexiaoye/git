#!/usr/bin/env python3
"""流水线：批量出表情 → 逐个动起来 → 拼预览图。一条命令跑完。

用法：
    python pipeline.py --outdir run1                       # 8 个情绪全跑
    python pipeline.py --outdir run1 --emotions 4 --size 320
    python pipeline.py --outdir run1 --animate bounce      # 额外给每张做弹跳 mp4
    python pipeline.py --outdir run1 --resume              # 断点续跑（默认就跳过已完成）

设计要点（见 learn/10-pipeline.md）：
- 幂等：产物存在就跳过，manifest.json 记录每一步状态
- 重试：API 与 ffmpeg 各自退避重试，不因单张失败中断整批
- 失败隔离：坏的记进 manifest，最后统一汇报
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:7860"
FFMPEG = r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe"

CHARACTER = ("chubby blue whale mascot, round body, cream white belly, tiny fins, "
             "small dot eyes, pink blush cheeks, thick clean outline")
STYLE = "chibi, flat color, cel shading, sticker, white background, masterpiece, best quality"
NEGATIVE = ("person, human, text, watermark, signature, lowres, bad anatomy, "
            "extra fins, multiple characters, extra character")

EMOTIONS = {
    "happy": "big happy smile, sparkling eyes",
    "deadpan": "deadpan unimpressed expression",
    "angry": "angry pouting, furrowed brows",
    "sleepy": "sleepy yawning, closed eyes",
    "lazy": "lying flat lazily",
    "cheer": "cheering happily, fins raised",
    "cry": "crying, tears streaming",
    "think": "thinking, looking up",
}


def retry(fn, tries: int = 3, delay: float = 2.0, what: str = "op"):
    last = None
    for i in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - 这里就是要兜住所有失败
            last = e
            print(f"  ! {what} 第 {i}/{tries} 次失败：{type(e).__name__}: {e}")
            if i < tries:
                time.sleep(delay * i)
    raise RuntimeError(f"{what} 重试耗尽：{last}")


def sd_gen(prompt: str, seed: int, size: int, steps: int) -> bytes:
    payload = {
        "prompt": prompt, "negative_prompt": NEGATIVE, "seed": seed,
        "width": size, "height": size, "steps": steps, "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }
    req = urllib.request.Request(API + "/sdapi/v1/txt2img",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return base64.b64decode(json.loads(r.read().decode())["images"][0])


def ffmpeg(args: list[str], timeout: int = 300) -> None:
    p = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=0x08000000,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "").strip().splitlines()[-1:] or ["ffmpeg failed"])


def animate(src: Path, dst: Path, mode: str, secs: float = 2.0) -> None:
    if mode == "bounce":
        ffmpeg([
            "-f", "lavfi", "-i", f"color=c=white:s={384}x{464}:d={secs}:r=30",
            "-loop", "1", "-i", str(src), "-t", str(secs),
            "-filter_complex",
            "[1:v]scale=384:384:force_original_aspect_ratio=decrease,format=rgba[fg];"
            "[0:v][fg]overlay=x=0:y='20+18*abs(sin(2*PI*t))',format=yuv420p[v]",
            "-map", "[v]", "-c:v", "libx264", "-crf", "20", str(dst),
        ])
    elif mode == "breathe":
        ffmpeg([
            "-loop", "1", "-i", str(src), "-t", str(secs), "-r", "30",
            "-vf", "scale=768:768,zoompan=z='1.0+0.03*sin(2*PI*on/45)':d=1:"
                   "s=384x384:fps=30,format=yuv420p",
            "-c:v", "libx264", "-crf", "20", str(dst),
        ])
    else:
        raise SystemExit(f"未知动画模式：{mode}")


def tile(paths: list[Path], out: Path, cols: int = 4) -> None:
    from PIL import Image

    imgs = [Image.open(p).convert("RGB") for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), "white")
    for i, im in enumerate(imgs):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(out)


def load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"items": {}}


def save_manifest(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="run")
    ap.add_argument("--emotions", type=int, default=len(EMOTIONS), help="取前 N 个情绪")
    ap.add_argument("--size", type=int, default=320)
    ap.add_argument("--steps", type=int, default=18)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--animate", choices=["none", "bounce", "breathe"], default="bounce")
    ap.add_argument("--resume", action="store_true", help="断点续跑（默认即跳过已完成）")
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    mf_path = outdir / "manifest.json"
    mf = load_manifest(mf_path)

    names = list(EMOTIONS)[: a.emotions]
    ok, failed = [], []

    for n, name in enumerate(names, 1):
        entry = mf["items"].setdefault(name, {})
        png = outdir / f"{n:02d}_{name}.png"
        mp4 = outdir / f"{n:02d}_{name}.mp4"

        # 步骤 1：出图（已存在就跳过）
        if entry.get("image") and png.exists():
            print(f"[{n}/{len(names)}] {name}: 图片已存在，跳过")
        else:
            print(f"[{n}/{len(names)}] {name}: 生成中 ...", flush=True)
            try:
                data = retry(lambda: sd_gen(f"{CHARACTER}, {EMOTIONS[name]}, {STYLE}",
                                            a.seed, a.size, a.steps), what=f"SD {name}")
                png.write_bytes(data)
                entry["image"] = {"path": png.name, "bytes": len(data)}
            except Exception as e:  # noqa: BLE001
                entry["image"] = {"error": str(e)}
                failed.append(name)
                save_manifest(mf_path, mf)
                continue

        # 步骤 2：动画
        if a.animate != "none":
            if entry.get("video") and mp4.exists():
                print(f"    {name}: 动画已存在，跳过")
            else:
                try:
                    retry(lambda: animate(png, mp4, a.animate), what=f"ffmpeg {name}")
                    entry["video"] = {"path": mp4.name, "bytes": mp4.stat().st_size}
                    print(f"    {name}: 动画完成 ({mp4.stat().st_size // 1024} KB)")
                except Exception as e:  # noqa: BLE001
                    entry["video"] = {"error": str(e)}
                    failed.append(name)

        if "error" not in entry.get("image", {}):
            ok.append(name)
        save_manifest(mf_path, mf)

    # 步骤 3：预览拼图
    pngs = [outdir / f"{i:02d}_{n}.png" for i, n in enumerate(names, 1) if (outdir / f"{i:02d}_{n}.png").exists()]
    if pngs:
        preview = outdir / "preview.png"
        retry(lambda: tile(pngs, preview), what="tile")
        print(f"[preview] {preview} ({preview.stat().st_size // 1024} KB)")

    # 汇总
    print("\n=== 汇总 ===")
    print(f"成功 {len(ok)} / 共 {len(names)}；失败 {len(failed)}：{', '.join(failed) or '无'}")
    print(f"清单：{mf_path}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
