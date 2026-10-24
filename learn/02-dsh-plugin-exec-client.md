# DSH 插件进阶：工具执行上下文 + 浏览器半侧（笔记 02）

> 学习日期：2026-10-25 · 来源：`dsh-sd-bridge-guard`（exec）与 `dsh-pet/src/client`（client 半侧）真实源码

## 一、工具的 `exec` 里有什么

实测 `execute(args, exec)` 的 `exec` 至少带 `agent`，而 `agent` 带 `session`：

```js
async execute(args, exec) {
  const session = exec && exec.agent && exec.agent.session
  // 用 session 定位当前会话（工作区、会话 id 等）
}
```

要点：
- **必须防御性取值**（`exec && exec.agent && ...`），不要假设一定存在
- 具体可用字段以宿主版本为准；拿不到就降级，不要让工具抛错

## 二、浏览器半侧的加载契约

这是最容易踩坑的部分：**client 产物不是 ESM 模块，而是一段普通脚本**。

```
lib/client.js   ← 由打包器产出，加载时自己往全局注册
```

```js
// 产物形态（源码里不能有顶层 import/export）
window.__ModuleLoader__.load({
  id: 'dsh-pet',                                  // 包名
  factory: (require) => {                         // require 是平台注入的
    const module = { exports: {} }
    const react = require('react')
    // ... 在这里 export const name / inject / apply
    return module.exports
  },
})
```

### 插件三件套在 client 半侧同样成立

`factory` 返回的对象仍然是 Cordis 插件形状：`name` / `inject` / `apply`。
`apply(ctx)` 里拿到的 `ctx` 是**浏览器侧**上下文（不是 Node 的），UI 通过插槽注册进去。

### `require` 只能取到「种子模块」

只包括：`react`、`react/jsx-runtime`、`react-dom`、`react-dom/client`、
`@deepseek-ai/dsh-client-*` 系列，以及 `package.json` 里 `dsh.client.inject` 显式声明的模块。

```json
{
  "exports": { "./client": "./lib/client.js" },
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" },
    "client": {
      "platform": "web",
      "inject": ["@deepseek-ai/dsh-client-connection", "@deepseek-ai/dsh-client-ui-slots"]
    }
  }
}
```

访问路径固定为 `/plugins/<包名>/client.js`。

## 三、踩坑清单（新增）

6. client 源码里写顶层 `import` / `export` → 加载即崩，必须打成 IIFE/普通脚本
7. `dsh.client.inject` 漏声明，运行时 `require('@deepseek-ai/dsh-client-xxx')` 直接抛错
8. 用 `require` 去要不在种子表里的包 → 拿不到；**取不到时要 try/catch 降级**（dsh-pet 就是取不到图标就退化成占位，绝不让整插件失败）
9. client 与 host 的 `apply` 上下文完全不同，别指望在 client 里访问文件系统

## 四、调试顺序（推荐）

1. 先只做 host 半侧，用工具跑通（`ctx.tools.register`）→ 确认 patch/id/name 三处一致
2. 再加 client 半侧，先 `console.log('loaded')` 验证 `/plugins/<包名>/client.js` 被拉到
3. 最后才挂 UI 插槽，一次只加一块界面

## 下一步（明天）

- 主题③ 起手：本机 SD 的参数体系（采样器/CFG/denoising 与画风的关系），结合工作区那套 SD 实测
