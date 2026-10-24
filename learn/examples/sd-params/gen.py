#!/usr/bin/env python3
"""SD 参数实验脚本：按「决策表」批量出图，固定 seed 做对照实验。

用法（SD 的 API 要先跑起来，默认 127.0.0.1:7860）：
    python gen.py                      # 用默认 preset
    python gen.py --preset draft       # 快速试构图
    python gen.py --preset final       # 定稿
    python gen.py --sampler "Euler a"  # 临时改单个参数

设计要点：
- 固定 seed：换参数时才可比（比较实验的第一原则）
- 只改一个变量：每次实验只动一处，其余沿用 preset
"""
import argparse
import base64
import json
import os
import urllib.request

API = os.environ.get("SD_API", "http://127.0.0.1:7860")

# 决策表（见 learn/03-sd-params.md）
PRESETS = {
    "draft": {
        "sampler_name": "Euler a",
        "steps": 20,
        "cfg_scale": 6.5,
        "denoising_strength": None,
    },
    "final": {
        "sampler_name": "DPM++ 2M Karras",
        "steps": 26,
        "cfg_scale": 7.0,
        "denoising_strength": None,
    },
    "ipic": {  # img2img：保画风改内容
        "sampler_name": "DPM++ 2M Karras",
        "steps": 24,
        "cfg_scale": 7.0,
        "denoising_strength": 0.45,
    },
}


def post(path, payload):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="final", choices=list(PRESETS))
    ap.add_argument("--prompt", default="chubby blue whale, cute mascot, chibi, flat color, white background")
    ap.add_argument("--negative", default="lowres, bad anatomy, bad hands, watermark, text, signature")
    ap.add_argument("--seed", type=int, default=12345)  # 固定，做对照
    ap.add_argument("--steps", type=int)
    ap.add_argument("--cfg", type=float)
    ap.add_argument("--sampler")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--outdir", default="out")
    a = ap.parse_args()

    p = dict(PRESETS[a.preset])
    if a.steps is not None:
        p["steps"] = a.steps
    if a.cfg is not None:
        p["cfg_scale"] = a.cfg
    if a.sampler:
        p["sampler_name"] = a.sampler

    payload = {
        "prompt": a.prompt,
        "negative_prompt": a.negative,
        "seed": a.seed,
        "width": a.width,
        "height": a.height,
        "steps": p["steps"],
        "cfg_scale": p["cfg_scale"],
        "sampler_name": p["sampler_name"],
        # None 会退回 0.75，img2img 场景必须显式给值
        **({} if p["denoising_strength"] is None else {"denoising_strength": p["denoising_strength"]}),
    }

    print("[req]", json.dumps(payload, ensure_ascii=False))
    res = post("/sdapi/v1/txt2img", payload)

    os.makedirs(a.outdir, exist_ok=True)
    name = f"{a.preset}_{p['sampler_name'].replace(' ', '')}_s{a.seed}_cfg{p['cfg_scale']}.png"
    path = os.path.join(a.outdir, name)
    with open(path, "wb") as f:
        f.write(base64.b64decode(res["images"][0]))

    info = json.loads(res.get("info", "{}"))
    print(f"[ok] {path}  seed={info.get('seed')}  sampler={info.get('sampler_name')}")


if __name__ == "__main__":
    main()
