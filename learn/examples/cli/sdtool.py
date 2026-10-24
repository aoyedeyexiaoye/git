#!/usr/bin/env python3
"""sdtool —— 把 SD 出图与 ffmpeg 剪辑包成一个可复用 CLI。

用法：
    python sdtool.py doctor
    python sdtool.py sd --prompt "chubby blue whale" --preset final
    python sdtool.py ff gif -i a.mp4 -o a.gif
    python sdtool.py ff trim -i a.mp4 -o b.mp4 --start 1 --duration 3

设计（详见 learn/05-cli-tool.md）：
- 配置分层：命令行 > --config JSON > 环境变量 > 默认值
- 外部命令集中重试 + 递增退避
- 退出码：0 成功 / 2 依赖不可用 / 3 重试耗尽
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("sdtool")

DEFAULTS = {
    "sd_api": "http://127.0.0.1:7860",
    "ffmpeg": r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe",
    "outdir": "out",
}

PRESETS = {
    "draft": {"sampler_name": "Euler a", "steps": 20, "cfg_scale": 6.5},
    "final": {"sampler_name": "DPM++ 2M Karras", "steps": 26, "cfg_scale": 7.0},
}

EXIT_OK, EXIT_ERR, EXIT_DEP, EXIT_RETRY = 0, 1, 2, 3


def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULTS)
    if path:
        p = Path(path)
        if not p.exists():
            raise SystemExit(f"配置文件不存在：{path}")
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    cfg["sd_api"] = os.environ.get("SD_API", cfg["sd_api"])
    cfg["ffmpeg"] = os.environ.get("FFMPEG", cfg["ffmpeg"])
    return cfg


def run(cmd: list[str], retries: int = 3, timeout: int = 600) -> str:
    """跑外部命令，失败重试（递增退避），耗尽后抛错。"""
    last = ""
    for i in range(1, retries + 1):
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=0x08000000 if os.name == "nt" else 0,  # 不弹黑框
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"命令不存在：{cmd[0]}") from e
        if p.returncode == 0:
            return p.stdout
        last = (p.stderr or p.stdout or "").strip().splitlines()[-1:] or [""]
        log.warning("第 %d/%d 次失败：%s", i, retries, last[0])
        if i < retries:
            time.sleep(2 * i)
    raise RuntimeError(f"重试耗尽：{cmd} :: {last}")


def http_json(url: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def cmd_doctor(cfg: dict) -> int:
    ok = True
    try:
        out = run([cfg["ffmpeg"], "-version"], retries=1, timeout=30)
        print(f"[ok]   ffmpeg: {out.splitlines()[0][:60]}")
    except Exception as e:
        print(f"[fail] ffmpeg: {e}")
        ok = False
    try:
        http_json(cfg["sd_api"] + "/sdapi/v1/options", timeout=8)
        print(f"[ok]   SD API: {cfg['sd_api']}")
    except Exception as e:
        print(f"[fail] SD API: {cfg['sd_api']} ({type(e).__name__})")
        ok = False
    return EXIT_OK if ok else EXIT_DEP


def cmd_sd(cfg: dict, a: argparse.Namespace) -> int:
    preset = dict(PRESETS[a.preset])
    payload = {
        "prompt": a.prompt,
        "negative_prompt": a.negative,
        "seed": a.seed,
        "width": a.width,
        "height": a.height,
        "sampler_name": a.sampler or preset["sampler_name"],
        "steps": a.steps or preset["steps"],
        "cfg_scale": a.cfg or preset["cfg_scale"],
    }
    log.info("请求 SD：%s", json.dumps({k: v for k, v in payload.items() if k != "prompt"}, ensure_ascii=False))
    res = http_json(cfg["sd_api"] + "/sdapi/v1/txt2img", payload)
    outdir = Path(a.outdir or cfg["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    import base64

    path = outdir / f"sd_{a.preset}_seed{a.seed}.png"
    path.write_bytes(base64.b64decode(res["images"][0]))
    print(f"[ok] {path}")
    return EXIT_OK


def cmd_img(cfg: dict, a: argparse.Namespace) -> int:
    """img2img：拿一张参考图按 denoising 强度重绘。"""
    import base64

    src = Path(a.input)
    if not src.exists():
        print(f"输入图不存在：{src}")
        return EXIT_ERR
    b64 = base64.b64encode(src.read_bytes()).decode()
    preset = dict(PRESETS[a.preset])
    payload = {
        "init_images": [b64],
        "prompt": a.prompt,
        "negative_prompt": a.negative,
        "denoising_strength": a.denoising,
        "seed": a.seed,
        "sampler_name": a.sampler or preset["sampler_name"],
        "steps": a.steps or preset["steps"],
        "cfg_scale": a.cfg or preset["cfg_scale"],
        "resize_mode": 0,
    }
    log.info("img2img denoising=%.2f seed=%d", a.denoising, a.seed)
    res = http_json(cfg["sd_api"] + "/sdapi/v1/img2img", payload)
    outdir = Path(a.outdir or cfg["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"img_{Path(a.input).stem}_d{a.denoising:.2f}.png"
    path.write_bytes(base64.b64decode(res["images"][0]))
    print(f"[ok] {path}")
    return EXIT_OK


def cmd_ff(cfg: dict, a: argparse.Namespace) -> int:
    ff = cfg["ffmpeg"]
    if a.action == "trim":
        cmd = [ff, "-y", "-ss", str(a.start), "-i", a.input, "-t", str(a.duration), "-c", "copy", a.output]
    elif a.action == "speed":
        sp = 1 / a.rate
        cmd = [ff, "-y", "-i", a.input, "-filter_complex",
               f"[0:v]setpts={sp}*PTS[v];[0:a]atempo={a.rate}[a]",
               "-map", "[v]", "-map", "[a]", a.output]
    elif a.action == "gif":
        cmd = [ff, "-y", "-i", a.input, "-vf", "fps=10,scale=320:-1:flags=lanczos", a.output]
    elif a.action == "text":
        vf = (f"drawtext=fontfile='C\\:/Windows/Fonts/msyh.ttc':text='{a.text}':"
              "fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-80")
        cmd = [ff, "-y", "-i", a.input, "-vf", vf, "-c:a", "copy", a.output]
    else:
        raise SystemExit(f"未知动作：{a.action}")
    run([c for c in cmd if c != ""], retries=2)
    size = Path(a.output).stat().st_size / 1024
    print(f"[ok] {a.output} ({size:.0f} KB)")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdtool", description="SD 出图 + ffmpeg 剪辑 一体化 CLI")
    p.add_argument("--config", help="JSON 配置文件路径")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="自检依赖")

    sd = sub.add_parser("sd", help="调 SD API 出图")
    sd.add_argument("--prompt", required=True)
    sd.add_argument("--negative", default="lowres, bad anatomy, bad hands, watermark, text")
    sd.add_argument("--preset", choices=list(PRESETS), default="final")
    sd.add_argument("--seed", type=int, default=12345)
    sd.add_argument("--width", type=int, default=512)
    sd.add_argument("--height", type=int, default=512)
    sd.add_argument("--sampler")
    sd.add_argument("--steps", type=int)
    sd.add_argument("--cfg", type=float)
    sd.add_argument("--outdir")

    img = sub.add_parser("img", help="img2img：按 denoising 重绘参考图")
    img.add_argument("-i", "--input", required=True, help="参考图路径")
    img.add_argument("--prompt", required=True)
    img.add_argument("--negative", default="lowres, bad anatomy, bad hands, watermark, text")
    img.add_argument("--denoising", type=float, default=0.45, help="0.3~0.5 保画风，0.7+ 重画")
    img.add_argument("--preset", choices=list(PRESETS), default="final")
    img.add_argument("--seed", type=int, default=12345)
    img.add_argument("--sampler")
    img.add_argument("--steps", type=int)
    img.add_argument("--cfg", type=float)
    img.add_argument("--outdir")

    ff = sub.add_parser("ff", help="ffmpeg 动作")
    ff.add_argument("action", choices=["trim", "speed", "gif", "text"])
    ff.add_argument("-i", "--input", required=True)
    ff.add_argument("-o", "--output", required=True)
    ff.add_argument("--start", type=float, default=0)
    ff.add_argument("--duration", type=float, default=0)
    ff.add_argument("--rate", type=float, default=2)
    ff.add_argument("--text", default="hello")
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    cfg = load_config(a.config)
    try:
        if a.cmd == "doctor":
            return cmd_doctor(cfg)
        if a.cmd == "sd":
            return cmd_sd(cfg, a)
        if a.cmd == "img":
            return cmd_img(cfg, a)
        if a.cmd == "ff":
            return cmd_ff(cfg, a)
    except RuntimeError as e:
        log.error("%s", e)
        return EXIT_RETRY
    except SystemExit:
        raise
    except Exception as e:  # 兜底，保证退出码可判
        log.error("未预期错误：%s", e)
        return EXIT_ERR
    return EXIT_ERR


if __name__ == "__main__":
    sys.exit(main())
