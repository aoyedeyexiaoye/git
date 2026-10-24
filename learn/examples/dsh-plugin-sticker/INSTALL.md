# 本地安装 / 卸载（dsh-sticker-pack）

DSH 的 profile 结构（实测）：

```
C:\Users\y\.dsh\profiles\desktop\
├─ package.json          # dependencies + dsh.profile.bundles（决定加载哪些层）
├─ cordis.patch.yml      # patch 层（id 级配置覆盖/禁用/插入）
├─ node_modules\         # 插件的实际落点
└─ cordis.yml / pnpm-*
```

## 安装（无 npm/pnpm 也能做）

```powershell
$prof = 'C:\Users\y\.dsh\profiles\desktop'
$src  = 'E:\AI\Deepseek1\learn\examples\dsh-plugin-sticker'

# 1) 备份
Copy-Item "$prof\package.json" "$prof\package.json.bak-dsh" -Force

# 2) 目录联接（等价于 file: 依赖的软链）
cmd /c "mklink /J `"$prof\node_modules\dsh-sticker-pack`" `"$src`""

# 3) 登记：依赖 + 层
#    dependencies 加  "dsh-sticker-pack": "file:E:/AI/Deepseek1/learn/examples/dsh-plugin-sticker"
#    dsh.profile.bundles 追加 "dsh-sticker-pack"
```

改完**重启 DSH** 生效（重启后 `sticker_pack` 工具才会出现）。

## 验证（不重启）

```powershell
$env:ELECTRON_RUN_AS_NODE='1'
cd C:\Users\y\.dsh\profiles\desktop
& 'E:\AI\Deepseek Harness.exe' --input-type=module -e "const m = await import('dsh-sticker-pack'); console.log(m.name, m.inject)"
# → sticker-pack [ 'tools' ]
```

## 卸载（回滚）

```powershell
$prof = 'C:\Users\y\.dsh\profiles\desktop'
cmd /c "rmdir `"$prof\node_modules\dsh-sticker-pack`""
Copy-Item "$prof\package.json.bak-dsh" "$prof\package.json" -Force
# 然后重启 DSH
```

## 注意

- 目录联接（junction）不需要管理员权限
- **改 profile 前一定备份 package.json**：写坏了 DSH 可能起不来
- 插件自身的 `cordis.patch.yml` 负责把它插进层栈，profile 里不用重复写
