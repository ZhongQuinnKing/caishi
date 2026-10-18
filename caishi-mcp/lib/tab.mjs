// 采诗 · tab — 浏览器引擎桥（opencli CLI 驱动，零 MCP 依赖）。
// 引擎解析顺序：包内 node_modules/.bin/opencli → 全局 PATH。
// 登录态复用引擎会话（会话名 caishi-<pid>，open 自动建、持久保留）。
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function findOpencliBin() {
  const localBin = path.join(pkgRoot, 'node_modules', '.bin', 'opencli');
  if (fs.existsSync(localBin)) return localBin;
  return 'opencli'; // 交给 PATH 解析
}

const OPENCLI_BIN = findOpencliBin();

// opencli 输出的「Update available」升级提示会混进 stdout，截断掉再解析。
function cleanStdout(text) {
  if (!text) return '';
  const lines = String(text).split(/\r?\n/);
  const cut = lines.findIndex((l) => /^\s*(Update available|Extension update|Run:|Download:)/.test(l));
  const kept = cut === -1 ? lines : lines.slice(0, cut);
  return kept.join('\n').trim();
}

function runOpencli(args, { timeoutMs = 90000 } = {}) {
  const r = spawnSync(OPENCLI_BIN, args, { encoding: 'utf8', timeout: timeoutMs, maxBuffer: 64 * 1024 * 1024 });
  if (r.error) throw new Error('opencli 引擎调用失败: ' + (r.error && r.error.message));
  const out = cleanStdout(r.stdout);
  if (r.status !== 0) {
    const err = cleanStdout(r.stderr) || '(无 stderr)';
    throw new Error('opencli 退出码 ' + r.status + ': ' + err.slice(0, 500));
  }
  return out;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// 页内 fetch 包装：与适配器原口径一致（同源自动附 cookie）。
function buildFetchJs(url) {
  return `(async () => {
    try {
      const res = await fetch(${JSON.stringify(url)}, { credentials: 'include' });
      const text = await res.text();
      return JSON.stringify({ __http: res.status, __body: text });
    } catch (e) { return JSON.stringify({ __netfail: String(e && e.message || e) }); }
  })()`;
}

export function createTab(session) {
  const sess = String(session || '').trim() || ('caishi-' + process.pid);
  const opencli = (cmd, ...rest) => runOpencli(['browser', sess, cmd, ...rest.map(String)]);
  return {
    // 打开 URL；waitUntil 只认 none（立即返回），settleMs 为页面静置时长
    async goto(url, { waitUntil, settleMs } = {}) {
      const out = opencli('open', url, '--window', 'background');
      const waitMs = Number(settleMs) || (waitUntil === 'none' ? 0 : 2000);
      if (waitMs > 0) await sleep(waitMs);
      return out;
    },
    // 当前页 URL
    async url() {
      return opencli('get', 'url');
    },
    // 页内执行 JS，原样返回表达式值（页面返回 JSON 字符串时由调用方解析）
    async evaluate(js) {
      return opencli('eval', js);
    },
    // 页内 fetch 并解析 JSON（用于站点公开 API；带登录态 cookie）
    async fetchJson(url) {
      const raw = opencli('eval', buildFetchJs(url));
      let parsed = null;
      try { parsed = JSON.parse(raw); } catch { /* 引擎偶发包裹，保底再剥一层 */ }
      if (parsed && typeof parsed === 'object' && typeof parsed.__body === 'string') {
        const body = parsed.__body;
        if (parsed.__http && parsed.__http >= 400) {
          const err = new Error('页内 fetch HTTP ' + parsed.__http);
          err.httpStatus = parsed.__http;
          throw err;
        }
        try { return JSON.parse(body); } catch { return body; }
      }
      return parsed;
    },
    // 会话名（调试/日志用）
    get session() { return sess; },
  };
}

export default createTab;
