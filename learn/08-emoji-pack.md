# 表情包批量生成与角色一致性（笔记 08）

> 学习日期：2026-10-25 · 本机实测（SD 127.0.0.1:7860，darkSushiMix）
> 目标：同一只角色、8 个情绪、统一画风，一次性产出

## 一、三段式提示词模板（可复用）

```
[角色块] + [情绪块] + [画风块]
```

| 块 | 内容 | 作用 |
|---|---|---|
| 角色块 | `chubby blue whale mascot, round body, cream white belly, tiny fins, small dot eyes, pink blush cheeks, thick clean outline` | 决定"是不是同一只" |
| 情绪块 | `crying, tears streaming, wobbly mouth` 等（**唯一变量**） | 决定表情 |
| 画风块 | `chibi, flat color, cel shading, sticker, white background, masterpiece` | 决定"像不像一套" |

负面词固定：`person, human, text, watermark, lowres, bad anatomy, extra fins, multiple characters`

## 二、8 个情绪一次跑完

```bash
python make_stickers.py --size 384 --steps 20 --seed 4242
# → out/01_happy.png ... out/08_think.png + out/00_all.png(1536x768 拼图)
```

结果：8 张全部出图，画风高度统一（同一套色、同一线宽、同白底），情绪也能读出来。
但——**同一 seed 并没有锁住角色长相**（下节展开）。

## 三、关键发现：同 seed ≠ 同一角色

用同一个 seed（4242）、只换情绪词跑 txt2img，得到的角色**形体/配色都在漂**：
有的偏白、有的整体发蓝；鳍的位置、身体轮廓、甚至头顶装饰都不同。
→ 结论：**txt2img 里决定"是谁"的是提示词与噪声路径，seed 只保证可复现，不保证身份**。

### 正确做法：以一张「角色基准图」做 img2img

| 做法 | 一致性 | 表现力 |
|---|---|---|
| txt2img + 同 seed（8 张独立生成） | ❌ 长相漂移明显 | ✅ 情绪夸张、好看 |
| **img2img（基准图 + denoise 0.5~0.6）** | ✅ 轮廓/配色基本不变 | ⚠️ 表情变化克制 |

对比图 `compare-consistency.png`（从左到右）：
1. 基准（deadpan）
2. txt2img「哭」→ 换了只角色
3. **img2img「哭」→ 还是同一只，只是多了眼泪**
4. txt2img「思考」→ 又换了一只，还凭空多了个粉色小挂件
5. **img2img「思考」→ 同一只，眼神上抬**

```bash
python sdtool.py img -i out/02_deadpan.png \
  --prompt "chubby blue whale mascot, crying, tears, chibi, flat color, sticker, white background" \
  --denoising 0.55 --seed 4242 --tag cry
```

## 四、推荐流水线（表情包）

1. **定妆照**：txt2img 出一张最满意的角色图（可多跑几张挑）
2. **批量表情**：以定妆照为输入，img2img `denoise 0.5~0.6`，每张只换情绪词
3. **微调**：某个表情不够到位 → 用 inpaint 只改嘴/眼所在的小框（`--mask-box`），denoise 0.5
4. **拼版**：PIL 4×2 拼图（脚本里 `tile()`），或 ffmpeg `hstack/vstack`

## 五、踩坑

32. **同 seed 不等于同角色**：换提示词词序/词义都会换人；要一致性必须靠 img2img/参考图
33. **模型爱加戏**：这批图里 4 张凭空出现粉色小挂件（兔子/螃蟹状），负面词要加 `extra character, accessory`
34. **同名覆盖**：我第一版 CLI 文件名只按「底图 + denoise」命名，跑第二个情绪时把第一个覆盖了——现在加了提示词短哈希 + `--tag` 后缀
35. 单张 384px 够用且快（8 张约 2 分钟），拼成 1536×768 当预览图正好

## 六、产物

```
examples/emoji/
├─ make_stickers.py          # 8 情绪批跑 + 4x2 拼图
├─ out/00_all.png            # 成品拼版
└─ compare-consistency.png   # txt2img vs img2img 一致性对比
```

## 下一步（明天）

- 主题⑨：把表情包做成**动态**——用 ffmpeg 给贴纸加位移/缩放/淡入，导出 GIF 与 MP4；顺便试 minterpolate 补帧
