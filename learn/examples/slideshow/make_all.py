#!/usr/bin/env python3
"""make_all.py —— 一条命令出成片：图片 → 运镜短片 → 字幕贴纸 → 配音 → BGM 闪避。

用法：
    python make_all.py --images ../emoji/out --project proj1
    python make_all.py --images ../emoji/out --project proj1 --only captions
    python make_all.py --images ../emoji/out --project proj1 --force

设计（复用第 10 轮的幂等 + manifest 思路）：
- 每步产物存在且比输入新 → 跳过（重跑只要 1 秒）
- manifest.json 记录每步状态、耗时、产物大小
- --only / --from 支持只跑某一步或从某步往后
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
PY = sys.executable

FFMPEG = r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe"


def run(cmd: list[str], what: str) -> None:
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=0x08000000)
    dt = time.time() - t0
    if p.returncode != 0:
        print(f"[fail] {what}（{dt:.1f}s）")
        print((p.stderr or p.stdout or "")[-800:])
        raise SystemExit(1)
    tail = [l for l in (p.stdout or "").splitlines() if l.strip()][-1:] or [""]
    print(f"[ok] {what}  {dt:.1f}s  {tail[0]}")


def newer(a: Path, b: Path) -> bool:
    """a 比 b 新（且都存在）→ 说明产物还可复用。"""
    return a.exists() and b.exists() and a.stat().st_mtime >= b.stat().st_mtime


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="图片目录")
    ap.add_argument("--project", default="proj", help="项目目录名（在 examples/slideshow 下）")
    ap.add_argument("--clip", type=float, default=2.5)
    ap.add_argument("--transition", type=float, default=0.5)
    ap.add_argument("--size", type=int, default=720)
    ap.add_argument("--title", default="大白饭表情包")
    ap.add_argument("--caption", action="append", default=[])
    ap.add_argument("--lines", default="", help="台词文件（起始秒|文本）；留空则不配音")
    ap.add_argument("--sticker", default="")
    ap.add_argument("--only", default="", choices=["", "video", "captions", "voice", "bgm"])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    imgs = Path(a.images).resolve()
    if not imgs.is_dir():
        raise SystemExit(f"图片目录不存在：{imgs}")
    proj = HERE / a.project
    proj.mkdir(parents=True, exist_ok=True)
    mf_path = proj / "manifest.json"
    mf = json.loads(mf_path.read_text(encoding="utf-8")) if mf_path.exists() else {"steps": {}}

    v1 = proj / "1_video.mp4"
    v2 = proj / "2_captions.mp4"
    v3 = proj / "3_voice.mp4"
    v4 = proj / "4_final.mp4"

    def mark(step: str, out: Path, extra: dict | None = None) -> None:
        mf["steps"][step] = {
            "output": out.name,
            "bytes": out.stat().st_size if out.exists() else 0,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **(extra or {}),
        }
        mf_path.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")

    def should(step: str, out: Path, deps: list[Path]) -> bool:
        if a.force:
            return True
        if a.only and a.only != step:
            return False
        # 产物比所有输入新 → 直接复用（即使这次没跑过，也认已有成果）
        if out.exists() and all(newer(out, d) for d in deps if d.exists()):
            return False
        if step not in mf["steps"]:
            return True
        return not all(newer(out, d) for d in deps if d.exists())

    # ① 图片 → 短片（运镜 + 转场）
    if should("video", v1, [imgs]):
        run([PY, str(HERE / "make_video.py"), "--indir", str(imgs), "--out", str(v1),
             "--clip", str(a.clip), "--transition", str(a.transition),
             "--size", str(a.size), "--exclude", "00_all"], "① 运镜短片")
        mark("video", v1, {"images": len(list(imgs.glob("*.png")))})

    # ② 字幕 / 标题 / 贴纸
    if should("captions", v2, [v1]):
        cmd = [PY, str(HERE / "captionize.py"), "-i", str(v1), "-o", str(v2), "--title", a.title]
        for c in a.caption:
            cmd += ["--caption", c]
        if a.sticker:
            cmd += ["--sticker", a.sticker, "--sticker-size", "130"]
        run(cmd, "② 字幕贴纸")
        mark("captions", v2, {"captions": len(a.caption)})

    # ③ 配音（可选）
    src = v2
    if a.lines:
        if should("voice", v3, [v2, Path(a.lines)]):
            run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(HERE / "voiceover.ps1"), "-Video", str(v2),
                 "-Out", str(v3), "-ScriptFile", str(Path(a.lines).resolve())], "③ 配音")
            mark("voice", v3)
        src = v3

    # ④ BGM + 闪避
    if should("bgm", v4, [src]):
        run([PY, str(HERE / "bgm_mix.py"), "-i", str(src), "-o", str(v4)], "④ BGM 闪避")
        mark("bgm", v4)

    print("\n=== 结果 ===")
    for f in (v1, v2, v3, v4):
        if f.exists():
            print(f"  {f.name:16} {f.stat().st_size // 1024:6} KB")
    print(f"  manifest: {mf_path}")


if __name__ == "__main__":
    sys.exit(main())
