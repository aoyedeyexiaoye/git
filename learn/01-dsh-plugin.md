# DSH 插件开发入门（笔记 01）

> 学习日期：2026-10-24 · 来源：本机已装插件的真实源码（`dsh-sd-bridge-guard`、`dsh-m`、`dsh-pet`）
> 目的：搞清一个 DSH 插件最少要有哪些文件、每个字段管什么

## 一句话结论

DSH 插件 = **一个 npm 包**，包里的 `package.json` 用 `dsh` 字段声明它是 bundle，
bundle 指向一个 `cordis.patch.yml` 注册层，层里按 id + 包名把插件挂进 profile。
宿主半侧（Node）是一个 Cordis 插件模块；浏览器半侧是可选的 `exports["./client"]`。

## 最小可运行结构

```
my-plugin/
├─ package.json
├─ cordis.patch.yml
└─ index.js          # 宿主半侧入口（package.json 的 main）
```

### package.json（关键字段）

```json
{
  "name": "dsh-my-plugin",
  "version": "0.1.0",
  "type": "module",
  "main": "index.js",
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" }
  },
  "peerDependencies": {
    "@deepseek-ai/cordis": "*"
  }
}
```

- `type: "module"` + `main` = Cordis 插件模块入口
- **`dsh.bundle.patch` 是必填的**：没它，安装后不会被挂进层栈，等于没装
- `peerDependencies` 里的 `@deepseek-ai/dsh-*` 由宿主提供，插件**不要**打包它们

### cordis.patch.yml

```yaml
- insert:
    - id: my-plugin            # 固定 id：配置覆盖、设置面板分组都按它
      name: dsh-my-plugin      # 包名，必须和 package.json 一致
```

### index.js（宿主半侧）

```js
export const name = 'my-plugin'      // 与 patch 里的 id 对应
export const inject = ['tools']      // 声明要用 ctx 上的哪个服务
export function apply(ctx, config = {}) {
  const off = ctx.tools.register({
    name: 'my_tool',
    description: '这个工具干什么（模型看这段决定何时调用）',
    parameters: {
      type: 'object',
      properties: { text: { type: 'string', description: '输入' } },
      required: ['text'],
    },
    async execute(args, exec) {
      return { content: [{ type: 'text', text: `收到：${args.text}` }] }
    },
  })
  ctx.on('dispose', () => off())
}
```

实测签名（来自 `dsh-sd-bridge-guard`）：
- `export function apply(ctx, config = {})`
- `ctx.tools.register(tool)`，返回注销函数
- tool 对象：`{ name, description, parameters, async execute(args, exec) }`

## 可选能力

| 能力 | 声明方式 | 说明 |
|---|---|---|
| 浏览器界面 | `exports["./client"]` + `dsh.client` | `dsh.client.platform: "web"`、`inject: [...]` 声明运行时依赖；访问路径 `/plugins/<包名>/client.js` |
| 市场图标 | `package.json` 的 `icon` | 只认 svg/png/jpg/jpeg/webp，≤256 KiB，必须在包目录内 |
| 版本兼容声明 | `dsh.compatibility.dshReleases` | 逐版本写 `compatible` / `incompatible`，只写范围不算证据 |

## 踩坑清单

1. `dsh.bundle.patch` 漏了 → 装了但不上层，最难排查
2. `cordis.patch.yml` 里的 `id` 和 `name` 不一致 → 挂载失败
3. `index.js` 的 `export const name` 必须等于 patch 的 `id`（不是包名）
4. 把 `@deepseek-ai/dsh-*` 打进 dependencies → 和宿主版本冲突
5. `execute` 返回值结构错（应是 `{ content: [...] }`）→ 模型收到空结果

## 下一步（明天）

- 补：`exec` 参数里有什么（上下文/取消信号/进度上报）
- 补：一个带 `client` 半侧的最小 UI 插件
