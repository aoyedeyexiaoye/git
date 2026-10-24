# 把 CLI 包成 DSH 插件工具（笔记 11）

> 学习日期：2026-10-25 · 产物 `examples/dsh-plugin-sticker/`，**不装进 DSH 也已验证通过**
> 目标：把前几天的 pipeline.py 变成聊天里一句话能调的工具

## 一、为什么"薄封装"是对的

我把流水线整个重写进插件？不——插件只做三件事：**拼参数 → 起进程 → 收结果**。

| 层 | 职责 | 好处 |
|---|---|---|
| 插件（index.js） | 参数校验、命令拼装、超时、结果摘要 | 换 UI/换模型都不用改算法 |
| 流水线（pipeline.py） | 出图、动画、清单、重试 | 命令行也能直接跑，便于调试 |

这样 `pipeline.py` 出问题时，你在终端就能复现，不用在插件里瞎猜。

## 二、工具契约（实测签名）

```js
export const name = 'sticker-pack'
export const inject = ['tools']

export function apply(ctx, config = {}) {
  const off = ctx.tools.register({
    name: 'sticker_pack',
    description: '……模型据此决定何时调用，要写清"能做什么 + 返回什么"',
    parameters: { type: 'object', properties: {...}, required: [] },
    async execute(args = {}) {
      return { content: [{ type: 'text', text: '结果摘要' }], isError: false }
    },
  })
  ctx.on('dispose', () => off())
}
```

要点：
- `inject: ['tools']` 声明依赖，没有它 `ctx.tools` 不存在
- `execute(args)` 返回 `{ content: [{type:'text', text}], isError }`，**别返回裸字符串**
- 注册返回的注销函数要挂到 `dispose` 上，否则热重载会重复注册

## 三、不装进 DSH 也能验证（本轮最实用的技巧）

两个问题一起解决：
1. **没装 Node**？DSH 自带的 Electron 可以直接当 Node 用（环境里有 `ELECTRON_RUN_AS_NODE=1`）
2. **不想为了测试装插件**？伪造 ctx 直接调 `apply`

```powershell
$env:ELECTRON_RUN_AS_NODE='1'
& 'E:\AI\Deepseek Harness.exe' test-plugin.mjs
```

```js
let tool = null
const fakeCtx = {
  tools: { register(t) { tool = t; return () => {} } },
  on() {},
}
apply(fakeCtx)
await tool.execute({ emotions: 1, dryRun: true })   // 先 dry-run 验命令
await tool.execute({ emotions: 1, size: 256 })      // 再真跑
```

实测输出：
```
plugin name = sticker-pack | inject = [ 'tools' ]
tool name = sticker_pack
params = emotions, size, steps, animate, outdir, dryRun
[dry-run] ...python.exe pipeline.py --outdir stickers_run --emotions 2 --size 256 ...
完成，耗时 17.0s
产物：...\_test_out
=== 汇总 === 成功 1 / 共 1；失败 0
```

**17 秒出图**，端到端通了。

## 四、三个必须处理的工程细节

1. **超时**：`spawnSync(..., { timeout: 30*60*1000 })`——出图可能跑 10 分钟，但必须有硬上限，否则卡死会话
2. **不弹窗**：`windowsHide: true`，否则每个调用闪一个黑框
3. **错误要能读**：失败时把 `stderr` 尾部一起返回，否则模型只看到"失败"没法修

## 五、dryRun 参数（强烈建议每个工具都加）

```js
if (args.dryRun) return { content: [{ type: 'text', text: `[dry-run] ${cmdline}` }] }
```

- 调试时先看命令对不对，**不烧算力**
- 模型也能先确认意图再执行，减少误操作

## 六、踩坑

46. `execute` 参数默认值要写 `args = {}`，否则模型不传参时直接 `Cannot read properties of undefined`
47. `spawnSync` 用 `python` 相对名，PATH 里没有就 ENOENT；**必须给绝对路径**
48. 忘记 `windowsHide` → 每次调用闪黑框，录屏/演示时很难看
49. 插件 `name`（export 的）必须等于 `cordis.patch.yml` 里的 `id`，否则挂载失败
50. 返回体里塞超长 stdout 会撑爆上下文——只回**尾部 8 行 + 产物路径**

## 七、产物

```
examples/dsh-plugin-sticker/
├─ package.json        # dsh.bundle.patch → cordis.patch.yml
├─ cordis.patch.yml    # id: sticker-pack
├─ index.js            # 工具注册 + spawn 流水线
├─ test-plugin.mjs     # 伪造 ctx 的验证脚本（不装即可跑）
└─ _test_out/          # 真跑产物（preview.png + manifest.json）
```

## 下一步（明天）

- 主题⑫：**把它真正装进 DSH**（本地打包 → 让 dsh-m 识别本地包），并在聊天里实测"出一套表情包"
- 需要解决：本地包如何进入 profile（npm pack / npm link / 手写层配置）
