// agent-frontend/agent-inject-plugin.js
// Vite 插件：在 luwang 的 index.html 中注入一行 <script>，
// 引导加载 inject.js（通过 Vite 的 /@fs/ 协议访问项目外的文件）。
// luwangfrontend 源码零改动。

import path from 'node:path'

/**
 * @param {{ agentRoot: string }} options
 */
export default function agentInjectPlugin({ agentRoot }) {
  // 用 posix 分隔符（Vite 的 /@fs/ 协议要求 forward slash）
  const injectAbs = path.join(agentRoot, 'inject.js').replace(/\\/g, '/')

  return {
    name: 'agent-inject',
    apply: 'serve',
    configResolved() {
      console.log('[agent-inject] plugin loaded, will inject:', '/@fs/' + injectAbs)
    },
    transformIndexHtml: {
      order: 'post',
      handler(html) {
        const tag = `<script type="module" src="/@fs/${injectAbs}"></script>`
        if (html.includes(tag)) return html
        // 塞在 </body> 前，保证 Vue app 先挂载
        if (html.includes('</body>')) {
          return html.replace('</body>', `  ${tag}\n  </body>`)
        }
        // 兜底：append
        return html + '\n' + tag
      },
    },
  }
}
