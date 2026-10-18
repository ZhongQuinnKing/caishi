#!/usr/bin/env node
// 采诗 · launcher — 自实现的 MCP stdio 服务器（JSON-RPC 2.0，行分隔帧）。
// 协议层全部本包自实现：initialize／tools/list／tools/call／ping／notifications，
// 不依赖任何 MCP SDK。浏览器引擎经 lib/tab.mjs 调 opencli CLI；
// 适配器在 mcp-adapters/（每站一目录），契约见 lib/adapter-sdk.mjs。
import readline from 'node:readline';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { createTab } from '../lib/tab.mjs';

const require = createRequire(import.meta.url);
const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pkg = require(path.join(pkgRoot, 'package.json'));

const SUPPORTED_PROTOCOLS = ['2024-11-05', '2025-03-26', '2025-06-18'];

// —— 命令行杂项（MCP 客户端传 --stdio 或什么都不传；其余给个说明） ——
const extraArgs = process.argv.slice(2);
if (extraArgs.length > 0) {
  const sub = extraArgs.find((a) => !a.startsWith('-')) || extraArgs[0];
  if (sub === 'setup') {
    console.log('[caishi-mcp] 自 1.3.0 起无需 setup：MCP 协议层为本包自实现。');
    console.log('[caishi-mcp] 浏览器引擎缺装时先执行：npm install -g @jackwener/opencli');
    process.exit(0);
  }
  if (sub === '--version' || sub === '-v') { console.log(pkg.version); process.exit(0); }
  if (sub === '--help' || sub === '-h') {
    console.log('caishi-mcp ' + pkg.version + ' — self-contained MCP server (stdio).');
    console.log('MCP 客户端配置：command=caishi-mcp（或 node bin/launch.mjs），无参数。');
    process.exit(0);
  }
}

// —— 适配器装载（按目录扫描，工具名 = 目录/文件名） ——
async function loadAdapters() {
  const adaptersDir = path.join(pkgRoot, 'mcp-adapters');
  const tools = [];
  if (!fs.existsSync(adaptersDir)) return tools;
  for (const dir of fs.readdirSync(adaptersDir).sort()) {
    const absDir = path.join(adaptersDir, dir);
    if (!fs.statSync(absDir).isDirectory()) continue;
    for (const f of fs.readdirSync(absDir).sort()) {
      if (!f.endsWith('.js')) continue;
      const name = dir + '/' + f.slice(0, -3);
      const mod = await import(pathToFileURL(path.join(absDir, f)).href);
      const def = mod.default || mod;
      if (!def || typeof def.run !== 'function') continue;
      tools.push({ name, def });
    }
  }
  return tools;
}

// —— args → JSON Schema ——
const TYPE_MAP = { string: 'string', int: 'integer', number: 'number', boolean: 'boolean', bool: 'boolean' };
function toInputSchema(args) {
  const properties = {};
  const required = [];
  for (const a of args || []) {
    properties[a.name] = {
      type: TYPE_MAP[a.type] || 'string',
      description: a.help || a.description || '',
    };
    if (a.required) required.push(a.name);
  }
  return { type: 'object', properties, required };
}

function toTool(t) {
  const def = t.def;
  return {
    name: t.name,
    description: def.description || '',
    inputSchema: toInputSchema(def.args),
  };
}

// —— 主循环（行分隔 JSON-RPC） ——
async function main() {
  const tools = await loadAdapters();
  const tabCache = new Map();

  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on('line', (line) => {
    line = line.trim();
    if (!line) return;
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (msg.id === undefined) {
      // notifications/initialized、notifications/cancelled 等：按协议不回。
      return;
    }
    const reply = (result) => write({ jsonrpc: '2.0', id: msg.id, result });
    const fail = (code, message) => write({ jsonrpc: '2.0', id: msg.id, error: { code, message } });

    switch (msg.method) {
      case 'initialize': {
        const reqProto = msg.params && msg.params.protocolVersion;
        const proto = SUPPORTED_PROTOCOLS.includes(reqProto) ? reqProto : '2024-11-05';
        reply({
          protocolVersion: proto,
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: pkg.name, version: pkg.version },
        });
        break;
      }
      case 'ping':
        reply({});
        break;
      case 'tools/list':
        reply({ tools: tools.map(toTool) });
        break;
      case 'tools/call': {
        const toolName = msg.params && msg.params.name;
        const args = (msg.params && msg.params.arguments) || {};
        const entry = tools.find((t) => t.name === toolName);
        if (!entry) { fail(-32602, '未知工具: ' + toolName); break; }
        let tab = tabCache.get('default');
        if (!tab) { tab = createTab('caishi-' + process.pid); tabCache.set('default', tab); }
        Promise.resolve()
          .then(() => entry.def.run({ tab, args }))
          .then((result) => {
            const text = JSON.stringify(result, null, 2);
            reply({ content: [{ type: 'text', text }], isError: false });
          })
          .catch((e) => {
            reply({
              content: [{ type: 'text', text: '工具执行失败: ' + (e && e.message ? e.message : String(e)) }],
              isError: true,
            });
          });
        break;
      }
      default:
        fail(-32601, '未知方法: ' + msg.method);
    }
  });
}

function write(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

main().catch((e) => {
  process.stderr.write('[caishi-mcp] 启动失败: ' + (e && e.message) + '\n');
  process.exit(1);
});
