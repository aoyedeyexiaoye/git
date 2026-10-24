# 下次改进清单

## 角色方向：更拟人（用户 2026-10-25 反馈）

当前形象是「圆滚滚的鲸鱼团子」，可爱但**不够拟人**——没有手、不能演动作、情绪只能靠眼睛和嘴。

下次改进方向（用户原话：要更拟人一点）：

1. **人形比例**：站立、两条腿、小手臂/手掌，能拿东西、能做手势
2. **服装/配饰**：连帽衫、围巾这类简单款式，比裸体团子更容易辨识
3. **表情自由度**：眉毛、嘴型、腮红可以拆开控，做成 8 情绪才不雷同
4. **保持辨识度**：蓝白配色 + 鲸鱼尾巴/鱼鳍作为记忆点，别做成"随便一个蓝发女孩"

两个待试的提示词方向（还没跑，下轮验证）：

```
A 拟人萌宠：anthropomorphic blue whale character, standing on two legs, small arms and hands,
  chibi proportions, big head, simple white hoodie, cel shading, thick outline, sticker,
  white background, masterpiece

B 人形角色：humanoid whale girl, blue hair, whale tail, chibi, big expressive eyes,
  casual outfit, full body, flat color, sticker, white background, masterpiece
```

## 顺手记两个工具坑

- `sdtool.py sd` 子命令**没有** `--size` / `--tag`（那是 `img` 子命令的参数），要用 `--width/--height`
- 出图很耗时，验证前先 `--steps 18 --width 384` 试跑，满意再上 512

## 视觉统一（上轮成片的问题）

- 运镜单一、配色不统一 → 下次给整片套一个统一的色调（ffmpeg `colorbalance`/`curves`）再出片
