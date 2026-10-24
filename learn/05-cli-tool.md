# 把命令包成 CLI（笔记 05）

> 学习日期：2026-10-25 · 产出：`examples/cli/sdtool.py`（本机跑通）
> 目标：把前几天的 ffmpeg / SD 命令从「复制粘贴」变成「可复用、可重试、有日志」的工具

## 一、为什么值得包一层

| 裸命令的问题 | 包一层后 |
|---|---|
| 参数记不住、拼错 | `--preset final` 语义化 |
| 路径硬编码 | 配置文件 + 环境变量回落 |
| 失败就停 | 重试 + 明确退出码 |
| 出了错不知道错在哪 | 结构化日志 |
| 想改就改代码 | 配置改一行 |

## 二、CLI 骨架（argparse 子命令）

```python
p = argparse.ArgumentParser(prog="sdtool")
sub = p.add_subparsers(dest="cmd", required=True)

sd = sub.add_parser("sd", help="调 SD API 出图")
sd.add_argument("--preset", choices=["draft", "final"], default="final")
sd.add_argument("--prompt", required=True)

ff = sub.add_parser("ff", help="ffmpeg 常用动作")
ff.add_argument("action", choices=["trim", "gif", "speed", "text"])
ff.add_argument("-i", "--input", required=True)
ff.add_argument("-o", "--output", required=True)

sub.add_parser("doctor", help="自检：ffmpeg 与 SD API 是否可用")
```

要点：
- `required=True` 在 `add_subparsers` 上，别漏——否则不带子命令也能跑进来
- 每个子命令只暴露「用户真的会改」的参数，其余从配置读

## 三、配置分层（优先级从高到低）

1. 命令行参数
2. `--config` 指定的 JSON
3. 环境变量（`SD_API`、`FFMPEG`）
4. 代码默认值

```python
cfg = {"sd_api": "http://127.0.0.1:7860", "ffmpeg": r"E:\AI\Deepseek1\tools\ffmpeg\ffmpeg.exe"}
if config_path and os.path.exists(config_path):
    cfg.update(json.load(open(config_path, encoding="utf-8")))
cfg["sd_api"] = os.environ.get("SD_API", cfg["sd_api"])
```

## 四、重试与退出码（外部命令必备）

```python
def run(cmd, retries=3, timeout=600):
    for i in range(1, retries + 1):
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        if p.returncode == 0:
            return p.stdout
        log.warning("第 %d 次失败：%s", i, p.stderr.strip().splitlines()[-1:])
        time.sleep(2 * i)          # 指数退避，别固定 sleep 1
    raise RuntimeError(f"命令失败：{cmd}")
```

退出码约定（脚本能被别的流程判断）：

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 一般错误（参数/文件不存在） |
| 2 | 外部依赖不可用（ffmpeg 缺失、API 没起） |
| 3 | 重试耗尽 |

## 五、Windows 上必须注意的 4 件事

1. **编码**：`subprocess` 一定要 `encoding="utf-8", errors="replace"`，否则中文输出直接 UnicodeDecodeError
2. **路径**：用 `pathlib.Path` 拼，别手写反斜杠；给子进程传 `str(path)` 并加引号交给 shell 时更要小心
3. **窗口闪黑框**：GUI 场景加 `creationflags=0x08000000`（CREATE_NO_WINDOW）
4. **脚本文件本身**：中文注释的 `.py` 没问题（Python3 默认 UTF-8）；但 `.ps1` 必须带 BOM

## 六、`doctor` 子命令的价值（最容易被省掉的一步）

先自检再干活，错误信息聚焦在「到底哪个依赖没准备好」：

```python
def doctor(cfg):
    ok = True
    try: run([cfg["ffmpeg"], "-version"], retries=1, timeout=20); print("[ok] ffmpeg")
    except Exception: print("[fail] ffmpeg"); ok = False
    try: http_get(cfg["sd_api"] + "/sdapi/v1/options", timeout=5); print("[ok] SD API")
    except Exception: print("[fail] SD API（可能没启动）"); ok = False
    return 0 if ok else 2
```

## 七、踩坑

20. `subprocess` 不指定 encoding → 中文报错/输出直接崩
21. 重试写死 `sleep(1)` → 对端限流时越试越糟，用递增退避
22. 只用 `print` 不用 `logging` → 输出重定向到文件后没有时间戳和级别，事后没法查
23. 把 API 密钥/路径写进代码 → 一律走配置或环境变量（仓库里绝不能有凭据）
24. `argparse` 里 `--foo` 与位置参数混用不做 `required` 校验 → 常常跑到一半才发现缺参数

## 下一步（明天）

- 主题⑥：SD 图生图与蒙版重绘的实战（拿一张现成图做风格迁移，记录 denoising 曲线）
