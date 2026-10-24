// 不装进 DSH 也能验证插件：伪造一个 ctx，抓取 register 到的工具，直接调 execute。
// 运行：ELECTRON_RUN_AS_NODE=1 "E:\AI\Deepseek Harness.exe" test-plugin.mjs
import { apply, name, inject } from './index.js'

let tool = null
const fakeCtx = {
  tools: {
    register(t) {
      tool = t
      return () => console.log('[dispose] tool unregistered')
    },
  },
  on(evt, fn) {
    console.log('[ctx.on]', evt)
  },
}

console.log('plugin name =', name, '| inject =', inject)
apply(fakeCtx)

if (!tool) {
  console.error('FAIL: 没有注册到工具')
  process.exit(1)
}

console.log('tool name =', tool.name)
console.log('params =', Object.keys(tool.parameters.properties).join(', '))

// 1) dryRun：只验证命令拼装
const dry = await tool.execute({ emotions: 2, size: 256, steps: 12, animate: 'none', dryRun: true })
console.log('\n[dryRun 输出]\n' + dry.content[0].text)

// 2) 真跑一张（最小参数），验证端到端
const real = await tool.execute({
  emotions: 1,
  size: 256,
  steps: 12,
  animate: 'none',
  outdir: 'E:\\AI\\Deepseek1\\learn\\examples\\dsh-plugin-sticker\\_test_out',
})
console.log('\n[real 输出]\n' + real.content[0].text)
console.log('isError =', real.isError)
