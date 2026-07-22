# db 环境配置（一次性初始化）

> 这是一份**环境配置**，不是任务。读完后你**只需做一件事**：用下面的信息完成 `configure()`，确认"已配置 token"，然后**待命**等待用户下达任务。
>
> **不要**因为读了本文件就自动查询数据、研判或生成报告。你的身份、能力和边界已由 `road_weather_agent` skill 常驻加载，这里只补充本机环境和鉴权信息。

## 环境

| 项目 | 地址 / 路径 |
|---|---|
| db 项目 | `F:/彩云/infero_glm_dev/infero_glm_dev` |
| 路网前端 | `http://localhost:8080`（`F:/彩云/luwang/luwangfrontend`） |
| 路网后端 | `http://118.121.196.98:8888`（`F:/彩云/luwang/luwangbackend`） |

平台接入函数在 `window.weatherPlatform`（详见 `weather_platform` skill）。

## 唯一要做的动作：配置

在一个 `/browser exec` 代码块里执行（token 仅用于本地调试，**不要展示、复述、总结或写入报告**）：

```js
await window.weatherPlatform.configure({
  base_url: 'http://118.121.196.98:8888',
  ui_base: 'http://localhost:8080',
  token: '<在此粘贴 luwang 登录 token>',
  remember_token: true
})
```

## 配置完成后

- 简要回复："已配置 token，已就绪，等待任务。"
- 可顺带用一句话说明你能做什么（数据查询 / 大屏联动 / 报告生成）。
- 以 `/call_for_trigger` 收尾待命，**不要**继续自循环或自造任务。
