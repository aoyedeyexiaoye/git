// dsh-sticker-pack —— 把本地流水线包成 DSH 工具
// 契约来自本机真实插件（dsh-sd-bridge-guard）源码：
//   export const name / export const inject / export function apply(ctx)
//   ctx.tools.register({ name, description, parameters, async execute(args, exec) })

import { spawnSync } from 'node:child_process'

export const name = 'sticker-pack'
export const inject = ['tools']

/** 默认路径：可用插件配置覆盖（apply 的第二个参数） */
const DEFAULTS = {
  python: 'E:\\AI\\Deepseek1\\py310\\python.exe',
  pipeline: 'E:\\AI\\Deepseek1\\learn\\examples\\pipeline\\pipeline.py',
  outdir: 'stickers_run',
}

function buildArgs(args, cfg) {
  const out = [cfg.pipeline, '--outdir', args.outdir || cfg.outdir]
  if (args.emotions) out.push('--emotions', String(args.emotions))
  if (args.size) out.push('--size', String(args.size))
  if (args.steps) out.push('--steps', String(args.steps))
  out.push('--animate', args.animate || 'bounce')
  return out
}

export function apply(ctx, config = {}) {
  const cfg = { ...DEFAULTS, ...config }

  const off = ctx.tools.register({
    name: 'sticker_pack',
    description:
      '生成一套表情包：调用本机 SD 出图 + ffmpeg 做成动图 + 拼预览图。' +
      '返回产物目录与 manifest 路径。dryRun=true 时只返回将执行的命令（不真正跑）。',
    parameters: {
      type: 'object',
      properties: {
        emotions: { type: 'integer', description: '生成前 N 个情绪（1-8，默认 4）', default: 4 },
        size: { type: 'integer', description: '单张边长像素（默认 320，快速预览用）', default: 320 },
        steps: { type: 'integer', description: '采样步数（默认 18）', default: 18 },
        animate: {
          type: 'string',
          enum: ['none', 'bounce', 'breathe'],
          description: '动效：none 只出静图 / bounce 弹跳 / breathe 呼吸',
          default: 'bounce',
        },
        outdir: { type: 'string', description: '产物目录（相对当前工作区或绝对路径）' },
        dryRun: { type: 'boolean', description: '只返回命令，不执行', default: false },
      },
      required: [],
    },

    async execute(args = {}) {
      const argv = buildArgs(args, cfg)
      const cmdline = [cfg.python, ...argv].join(' ')

      if (args.dryRun) {
        return { content: [{ type: 'text', text: `[dry-run] ${cmdline}` }] }
      }

      const t0 = Date.now()
      const p = spawnSync(cfg.python, argv, {
        encoding: 'utf8',
        timeout: 30 * 60 * 1000, // 30 分钟硬上限，批量出图可能较久
        windowsHide: true,
      })

      if (p.error) {
        return {
          content: [{ type: 'text', text: `启动失败：${p.error.message}\n命令：${cmdline}` }],
          isError: true,
        }
      }
      const out = (p.stdout || '').trim()
      const err = (p.stderr || '').trim()
      const tail = out.split('\n').slice(-8).join('\n')
      const ok = p.status === 0
      return {
        content: [
          {
            type: 'text',
            text:
              `${ok ? '完成' : `失败（exit ${p.status}）`}，耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s\n` +
              `产物：${args.outdir || cfg.outdir}\n--- 尾部输出 ---\n${tail}` +
              (err ? `\n--- stderr ---\n${err.split('\n').slice(-5).join('\n')}` : ''),
          },
        ],
        isError: !ok,
      }
    },
  })

  ctx.on('dispose', () => off())
}
