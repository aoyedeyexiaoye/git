# 图生图与 denoising 曲线（笔记 06）

> 学习日期：2026-10-25 · 全部为本机实测（SD 在 127.0.0.1:7860，模型 darkSushiMix）
> 方法：同一张底图 + 同一句提示词 + 同一 seed（777），**只改 denoising**

## 一、实验设置

| 项 | 值 |
|---|---|
| 底图 | `sample-blue-whale.png`（512×512，上一轮文生图产物） |
| 提示词 | `chubby blue whale mascot, watercolor painting, soft paper texture, pastel palette` |
| 采样器 / 步数 | Euler a（draft preset）/ 20 |
| seed | 777（三组一致） |
| 变量 | denoising = 0.35 / 0.55 / 0.75 |

## 二、结果：相似度可以量化

用 ffmpeg 的 `ssim` 滤镜对比「重绘图 vs 原图」（1.0 = 完全相同）：

```bash
ffmpeg -i out.png -i src.png -lavfi ssim -f null -
```

| denoising | SSIM（越高越像原图） | 肉眼观察 |
|---|---|---|
| 0.35 | **0.947** | 几乎不变，只多了水彩纸纹与柔光，轮廓/表情原封不动 |
| 0.55 | **0.864** | 明显水彩化：笔触、色块浮现，鳍的位置和眼睛形状开始变化，但仍是同一只胖鱼 |
| 0.75 | **0.712** | **重画**：变成跃起的写实水彩鲸，只剩「居中的蓝白团块 + 白底」这个构图骨架 |

这组数字把「0.4-0.5 保画风 / 0.7+ 重画」的经验落成了可测量的事实。

## 三、实操结论

1. **想保住角色设定**（同一只吉祥物换个画风）→ `denoising 0.35~0.45`，SSIM 会落在 0.9 以上
2. **想要同一构图的另一种画法** → `0.55~0.65`，SSIM 0.85 左右，形态开始松动人仍认得出
3. **只借构图**（重新演绎）→ `0.75+`，SSIM 掉到 0.7 附近，别指望它长得像
4. **别用 SSIM 当唯一标准**：0.75 那张 SSIM 0.712，但它其实是我最喜欢的——**数值只回答"像不像"，不回答"好不好"**

## 四、可比实验的三条纪律

1. 一次只改一个变量（这次只动 denoising）
2. seed 固定（不然差异可能全来自 seed）
3. 提示词固定（提示词一改，画风变化就说不清是谁造成的）

## 五、怎么调（CLI 已支持）

```bash
# 单张
python sdtool.py img -i base.png --prompt "watercolor, soft paper texture" --denoising 0.45

# 扫曲线（固定 seed，只变 denoising）
for d in 0.35 0.55 0.75; do
  python sdtool.py img -i base.png --prompt "..." --denoising $d --seed 777 --outdir out
done
```

产物命名自带参数（`img_<底图名>_d0.35.png`），事后不用猜是哪组参数。

## 六、踩坑

25. `resize_mode` 不显式传 0，A1111 可能按设置缩放到目标分辨率，导致构图被裁
26. 底图用 base64 直传时不要超过 API 体积限制；大图先缩到目标尺寸再传
27. `denoising=0.3` 以下基本等于「加滤镜」，想改内容别在这档浪费时间

## 七、还没做的（下次）

- **蒙版重绘（inpaint）**：只改局部时，`img2img` 会把整张图重绘掉，必须走 mask 接口
- 计划：给 CLI 加 `--mask-box x,y,w,h`，重绘蓝鲸某一块（比如给它加顶帽子），并对比 0.4/0.6 两档

## 下一步（明天）

- 主题⑦：蒙版重绘实战 + 把表情包做出来（8 个情绪，统一角色）
