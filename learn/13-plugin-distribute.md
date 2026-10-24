# 插件分发：没有 npm 也能打出标准 tarball（笔记 13）

> 学习日期：2026-10-25 · 实测：`tar` 手工打包 → 解包 → 成功 import
> 目标：让插件能"发给别人 / 装到别台机器"，而不是只能在本机软链

## 一、npm pack 的产物到底是什么

就是一个 **tar.gz，根目录固定叫 `package/`**：

```
dsh-sticker-pack-0.1.0.tgz
└─ package/
   ├─ package.json
   ├─ cordis.patch.yml
   ├─ index.js
   ├─ INSTALL.md
   └─ test-plugin.mjs
```

知道这一点，没有 npm 也能手工造：

```powershell
$tmp = '...\ .pack'
New-Item -ItemType Directory "$tmp\package" -Force | Out-Null
# 只拷 package.json 的 files[] 里列的文件
Copy-Item package.json,cordis.patch.yml,index.js,INSTALL.md,test-plugin.mjs "$tmp\package"
& tar.exe -czf dsh-sticker-pack-0.1.0.tgz -C $tmp package
```

实测：**2.1 KB**（只含 `files[]` 白名单里的 3 个文件）。

> 手工打包时我还多塞了 `INSTALL.md`、`test-plugin.mjs`，包变成 3.5 KB——
> 这正是 `files[]` 白名单的意义：**npm 只打白名单里的东西**，多塞的东西在真实发布里会被丢掉。
> 所以我写了 `pack.ps1` 按 `files[]` 打包，并校验"列了但不存在"的情况直接报错。

## 二、打完必须验"能装能引"

光看体积不算验证。解包到模拟的 `node_modules` 再 import：

```powershell
mkdir node_modules; tar -xzf pkg.tgz -C node_modules
mv node_modules/package node_modules/dsh-sticker-pack     # ← 关键：npm 会做这步重命名
$env:ELECTRON_RUN_AS_NODE='1'
& 'E:\AI\Deepseek Harness.exe' --input-type=module -e "const m=await import('dsh-sticker-pack'); console.log(m.name)"
```

实测输出：`tarball 可解析: sticker-pack [ 'tools' ]`

## 三、三种分发的取舍

| 方式 | 适用 | 优点 | 代价 |
|---|---|---|---|
| `file:` + junction | 本机开发 | 改完立即生效，无需重装 | 只在本机、路径写死 |
| **tarball（本轮）** | 发给别人 / 另一台机器 | 单文件、可校验、离线可装 | 每次改动要重新打包 |
| npm registry | 公共分发 | 版本管理、`dsh-m install` 直接认 | 要发布流程与账号 |

## 四、版本号纪律

- 改代码不兼容 → `0.1.0 → 0.2.0`
- 修 bug/加参数 → `0.1.0 → 0.1.1`
- **tarball 文件名必须带版本**，否则两个版本混在一起分不清
- `package.json` 的 `files[]` 是白名单：**漏写 = 打不进包**（我第一次就差点把 `cordis.patch.yml` 漏了，那样装上就是个"哑"插件）

## 五、踩坑

56. 忘了把解压出的 `package/` 重命名成包名 → `import` 报 `ERR_MODULE_NOT_FOUND`
57. `tar` 在 Windows 上要显式 `-C` 指定根目录，否则会把绝对路径打进去（解包后路径乱七八糟）
58. `files[]` 与真实打包含义不一致 → 本地能跑、装到别人机器就少文件
59. 用 `.zip` 而不是 `.tgz` → 大多数包管理器不认
60. 打完包忘记删中间目录 `.pack/` → 下次 `tar -C` 可能把上次残留也打进去

## 六、产物

```
examples/dsh-plugin-sticker/
├─ pack.ps1                        # 一键打包（含 files[] 读取与校验）
└─ dsh-sticker-pack-0.1.0.tgz      # 可分发 tarball
```

## 下一步（明天）

- DSH 重启后实测 `sticker_pack` 工具
- 之后：把 `learn/` 的笔记做成站点（vitepress/静态页）
