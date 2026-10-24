# 把本地插件真装进 DSH（笔记 12）

> 学习日期：2026-10-25 · 本机实测（profile: `C:\Users\y\.dsh\profiles\desktop`）
> 目标：不用 npm 发布，把本地插件包挂进 DSH 并让它能被解析

## 一、profile 到底长什么样（实测）

```
C:\Users\y\.dsh\profiles\desktop\
├─ package.json         ← ① dependencies ② dsh.profile.bundles（层顺序）
├─ cordis.patch.yml     ← 用户 patch 层：按 id 覆盖配置/禁用/插入
├─ node_modules\        ← 插件实际落点
├─ cordis.yml           ← 基础层
└─ pnpm-lock.yaml       ← 依赖锁
```

`package.json` 里两个关键位置：

```json
{
  "dependencies": { "dsh-sticker-pack": "file:E:/AI/.../dsh-plugin-sticker" },
  "dsh": { "profile": { "bundles": ["@deepseek-ai/dsh-base", "...", "dsh-sticker-pack"] } }
}
```

- **dependencies** 决定"包在哪"
- **bundles** 决定"加载哪些层、什么顺序"（漏了它：装了但不生效）

## 二、没有 npm/pnpm 时的三条等效操作

机器上没有 node/npm/pnpm（只有 DSH 自带 Electron），所以走手工路线：

| 正规做法 | 手工等效 | 实际用的 |
|---|---|---|
| `pnpm add file:../pkg` | 目录联接（junction）进 `node_modules` | ✅ `mklink /J` |
| 自动写 package.json | 手工加 dependencies 项 | ✅ |
| `pnpm install` | 无需（已软链） | — |

```powershell
cmd /c "mklink /J `"$prof\node_modules\dsh-sticker-pack`" `"$src`""
```

junction **不需要管理员权限**，而 `New-Item -ItemType SymbolicLink` 需要开发者模式/管理员。

## 三、验证顺序（别一上来就重启）

1. **模块自身**：`node test-plugin.mjs`（伪造 ctx，验工厂与工具）
2. **解析**：在 profile 目录里 `import('dsh-sticker-pack')`，确认能拿到 `name/inject/apply`
3. **重启后**：工具是否出现在会话里

第 2 步实测输出：

```
resolved: sticker-pack | inject: ["tools"] | has apply: true
```

## 四、安全边界（重要）

- 改 `package.json` **前必须备份**：JSON 写坏 → DSH 起不来 → 你只能手改回来
- 插件加载失败不一定拖垮 DSH，但**层里任何一环崩都可能让整个 profile 停摆**
- 回滚只需要两步：删 junction + 还原 package.json

## 五、踩坑

51. 只把包放进 `node_modules` 不写 `dsh.profile.bundles` → **静默不生效**，最难查
52. 用符号链接（`SymbolicLink`）而非联接（`Junction`）→ 普通用户权限不足直接失败
53. 改完不重启 → 你会以为"插件没写对"，其实是没加载
54. `dependencies` 里的 `file:` 路径要用**正斜杠**（Windows 反斜杠在 JSON 里要转义，容易写错）
55. 备份文件名别叫 `package.json.backup`（有些工具会去扫 `*.json` 前缀匹配），用 `.bak-dsh` 这种不会被误读的名字

## 六、产物

```
examples/dsh-plugin-sticker/
├─ INSTALL.md          # 安装/验证/回滚三件套
└─ （package.json / cordis.patch.yml / index.js / test-plugin.mjs）
```

profile 侧已登记：`dependencies` 增加 `dsh-sticker-pack`，`bundles` 追加同名项，`node_modules` 建立联接。

## 下一步（明天）

- 重启后实测：在聊天里直接调 `sticker_pack`，看模型是否会自己想到用它
- 再补：把它做成**可分发**的形式（npm pack 出 tarball，便于以后给别人/给别台机器装）
