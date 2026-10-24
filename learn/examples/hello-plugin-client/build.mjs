// 打包 client 半侧：产出 lib/client.js（普通脚本，自己往 __ModuleLoader__ 注册）
// 依赖：esbuild（devDependency）  →  npm i -D esbuild && node build.mjs
import { build } from 'esbuild'
import { mkdirSync } from 'node:fs'

mkdirSync('lib', { recursive: true })

await build({
  entryPoints: ['entry.ts'],
  outfile: 'lib/client.js',
  bundle: true,
  format: 'iife', // 关键：不能是 esm
  platform: 'browser',
  target: 'es2022',
  globalName: 'HelloPluginClient',
  // 平台种子模块由宿主提供，不打包
  external: ['react', 'react/jsx-runtime', 'react-dom', 'react-dom/client'],
  logLevel: 'info',
})

console.log('built -> lib/client.js')
