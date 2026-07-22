// agent-frontend/vite.config.js
// 外部 Vite 配置：以 luwangfrontend 为 root 目录启动，合并原配置 + 注入插件。
// luwangfrontend 源码零改动，git pull 无冲突。
//
// 启动：
//   cd <path-to-luwang-frontend>
//   npx vite --config <path-to-this-file>
//
// 环境变量：
//   LUWANG_FRONTEND_PATH  luwangfrontend 目录（默认解析为 ../../../luwang/luwangfrontend）

import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

import agentInjectPlugin from './agent-inject-plugin.js'

// 本插件包所在目录
const AGENT_ROOT = path.dirname(fileURLToPath(import.meta.url))

// luwangfrontend 目录（默认相对结构：F:/彩云/{luwang,infero_glm_dev/infero_glm_dev/agent-frontend}）
const DEFAULT_LUWANG_PATH = path.resolve(AGENT_ROOT, '../../../luwang/luwangfrontend')
const LUWANG_ROOT = path.resolve(
  process.env.LUWANG_FRONTEND_PATH || DEFAULT_LUWANG_PATH
)
const LUWANG_CONFIG_FILE = path.join(LUWANG_ROOT, 'vite.config.js')

if (!fs.existsSync(LUWANG_CONFIG_FILE)) {
  throw new Error(
    `[agent-frontend] luwangfrontend/vite.config.js not found under: ${LUWANG_ROOT}\n` +
      `Set env LUWANG_FRONTEND_PATH to override, or clone luwangfrontend there.`
  )
}

// 用 luwang 目录的 require，让 mergeConfig / loadConfigFromFile 走它那份 vite（版本一致）
const require = createRequire(path.join(LUWANG_ROOT, '/'))
const { mergeConfig, loadConfigFromFile } = require('vite')

export default async ({ mode, command }) => {
  // 由 Vite 自己 (走 esbuild) 加载 luwang 的 config，兼容 alias / 缺扩展名等
  const loaded = await loadConfigFromFile(
    { command: command || 'serve', mode: mode || 'development' },
    LUWANG_CONFIG_FILE,
    LUWANG_ROOT
  )
  const baseConfig = (loaded && loaded.config) || {}

  return mergeConfig(baseConfig, {
    // 关键：root 指向 luwang 前端，让 index.html / src/main.js 全部按原样解析
    root: LUWANG_ROOT,
    configFile: false,
    server: {
      open: true,
      fs: {
        allow: [LUWANG_ROOT, AGENT_ROOT],
      },
    },
    resolve: {
      alias: {
        '@agent': AGENT_ROOT,
      },
    },
    plugins: [
      agentInjectPlugin({ agentRoot: AGENT_ROOT }),
    ],
  })
}
