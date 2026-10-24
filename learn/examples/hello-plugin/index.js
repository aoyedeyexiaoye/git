// 最小 DSH 插件示例：注册一个 hello 工具
// 签名来自本机 dsh-sd-bridge-guard 实测：apply(ctx, config) + ctx.tools.register(tool)

export const name = 'hello-plugin' // 必须等于 cordis.patch.yml 里的 id
export const inject = ['tools']

export function apply(ctx, config = {}) {
  const off = ctx.tools.register({
    name: 'hello',
    description: '示例工具：把传入的文字原样回显，用于验证插件是否被正确加载',
    parameters: {
      type: 'object',
      properties: {
        text: { type: 'string', description: '要回显的文字' },
      },
      required: ['text'],
    },
    async execute(args) {
      return {
        content: [{ type: 'text', text: `hello: ${args.text}` }],
      }
    },
  })

  ctx.on('dispose', () => off())
}
