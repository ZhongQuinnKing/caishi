// 采诗 · adapter-sdk — 自实现的适配器契约（替代 opencli-mcp/adapter-sdk）。
// 契约与 opencli-mcp 保持同构：defineAdapter(config) 原样带回，
// run({ tab, args }) 为执行体；tab 由本包 lib/tab.mjs 提供（opencli 引擎桥）。
export function defineAdapter(config) {
  if (!config || typeof config !== 'object') throw new Error('defineAdapter 需要配置对象');
  if (!config.description || typeof config.run !== 'function') {
    throw new Error('适配器缺 description 或 run');
  }
  if (!Array.isArray(config.args)) config.args = [];
  return config;
}

export default defineAdapter;
