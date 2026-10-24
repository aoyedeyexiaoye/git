#!/usr/bin/env python3
"""表情包批量生成：同一角色、8 个情绪、统一画风，最后拼成 4x2 大图。

用法：
    python make_stickers.py                # 出 8 张 + 拼图
    python make_stickers.py --seed 4242    # 换种子家族

设计（详见 learn/08-emoji-pack.md）：
- 角色块（长相）+ 画风块（质感）+ 情绪块（变量）三段式提示词
- 全部用同一 seed：保证长相/构图尽量一致
- 统一负面词：防文字水印、防多人、防畸形
"""
from __future__ import annotations

import argparse
import base64
import json
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:7860"

# ① 角色块：决定"是不是同一只"
CHARACTER = (
    "chubby blue whale mascot, round body, cream white belly, tiny fins, "
    "small dot eyes, pink blush cheeks, thick clean outline"
)
# ② 画风块：决定"像不像一套"
STYLE = "chibi, flat color, cel shading, sticker, white background, simple composition, masterpiece, best quality"
# ③ 情绪块：唯一变量
EMOTIONS = {
    "happy": "big happy smile, sparkling eyes",
    "deadpan": "deadpan unimpressed expression, half-closed eyes",
    "angry": "angry pouting, furrowed brows",
    "sleepy": "sleepy yawning, closed eyes, tiny snot bubble",
    "lazy": "lying flat lazily, relaxed face",
    "cheer": "cheering happily, fins raised up",
    "cry": "crying, tears streaming, wobbly mouth",
    "think": "thinking, looking up, small question mark floating",
}

NEGATIVE = (
    "person, human, anime girl, face, text, watermark, signature, lowres, "
    "bad anatomy, extra fins, deformed, multiple characters, photorealistic"
)


def gen(prompt: str, seed: int, steps: int, size: int) -> bytes:
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "seed": seed,
        "width": size,
        "height": size,
        "steps": steps,
        "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }
    req = urllib.request.Request(
        API + "/sdapi/v1/txt2img",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as r:
        res = json.loads(r.read().decode())
    return base64.b64decode(res["images"][0])


def tile(paths: list[Path], out: Path, cols: int = 4) -> None:
    from PIL import Image

    imgs = [Image.open(p).convert("RGB") for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), (255, 255, 255))
    for i, im in enumerate(imgs):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(out)
    print(f"[sheet] {out} ({sheet.size[0]}x{sheet.size[1]})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=4242, help="所有表情共用同一 seed")
    ap.add_argument("--steps", type=int, default=22)
    ap.add_argument("--size", type=int, default=384, help="单张边长（384 拼 4x2 正好 1536x768）")
    ap.add_argument("--outdir", default="stickers")
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for i, (name, emo) in enumerate(EMOTIONS.items()):
        prompt = f"{CHARACTER}, {emo}, {STYLE}"
        print(f"[{i+1}/{len(EMOTIONS)}] {name} ...", end=" ", flush=True)
        data = gen(prompt, a.seed, a.steps, a.size)
        p = outdir / f"{i+1:02d}_{name}.png"
        p.write_bytes(data)
        paths.append(p)
        print(f"{p.name} ({len(data)//1024} KB)")

    tile(paths, outdir / "00_all.png")
    print("[done]")


if __name__ == "__main__":
    main()
