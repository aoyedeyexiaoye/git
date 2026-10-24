// 示例：client 半侧入口（源码形态，打包后给 __ModuleLoader__ 用）
// 注意：本文件由打包器处理，产物里不能有顶层 import/export 之外的 ESM 语义
import type * as ReactNS from 'react'

export function makeFactory(): (require: (m: string) => unknown) => unknown {
  return (require) => {
    const react = require('react') as typeof ReactNS
    const h = react.createElement

    const module = { exports: {} as Record<string, unknown> }

    // 插件三件套（浏览器侧上下文）
    Object.assign(module.exports, {
      name: 'hello-plugin-client',
      inject: [],
      apply(ctx: unknown) {
        // 这里拿到的 ctx 是浏览器侧上下文；UI 通过插槽注册。
        // 最小验证：先只打日志，确认 client.js 被加载。
        // eslint-disable-next-line no-console
        console.log('[hello-plugin] client half loaded', ctx)

        // 极简块：往页面右下角塞一行字（真实场景应走 slots 插槽）
        const el = document.createElement('div')
        el.textContent = 'hello from hello-plugin'
        el.style.cssText =
          'position:fixed;right:12px;bottom:12px;z-index:9999;padding:6px 10px;border-radius:8px;background:#1f6feb;color:#fff;font:12px/1.4 sans-serif;'
        document.body.appendChild(el)

        return h('span', null, 'hello-plugin')
      },
    })

    return module.exports
  }
}
