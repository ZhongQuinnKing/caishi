#!/usr/bin/env node
// 采诗 · launcher — npx 一条命令即可作为 MCP 服务器运行。
// 职责：①把包内适配器同步到 ~/.opencli-mcp/adapters/（用户源，覆盖内置的同类目）
//       ②原样代理 stdio 跑 opencli-mcp（浏览器桥本体）。
// 设计说明：适配器同步幂等且仅几分之一秒，每次启动都做，保证“装完即最新”。
import { spawnSync, spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function die(msg) {
  console.error('[caishi-mcp] ' + msg);
  process.exit(1);
}

// —— 同步适配器到用户源（先做：即便依赖缺失也不半装） ——
const adaptersSrc = path.join(pkgRoot, 'mcp-adapters');
const adaptersDst = path.join(os.homedir(), '.opencli-mcp', 'adapters');
try {
  if (fs.existsSync(adaptersSrc)) {
    for (const site of fs.readdirSync(adaptersSrc)) {
      const from = path.join(adaptersSrc, site);
      if (!fs.statSync(from).isDirectory()) continue;
      const to = path.join(adaptersDst, site);
      fs.mkdirSync(to, { recursive: true });
      for (const f of fs.readdirSync(from)) {
        if (f.endsWith('.js')) fs.copyFileSync(path.join(from, f), path.join(to, f));
      }
    }
  }
} catch (e) {
  // 适配器同步失败不致命：可能是目录权限等；如实提示并继续。
  console.error('[caishi-mcp] 适配器同步告警: ' + (e && e.message));
}

// —— 定位 opencli-mcp 入口（本包依赖，装包即在本；缺失才回退全局安装） ——
// 注意：opencli-mcp 的 exports 白名单不含 ./package.json，不能直接 resolve 它；
// 从允许的子路径（./adapter-sdk）向上找回包根。
function findPkgRoot(fromFile) {
  let dir = path.dirname(fromFile);
  for (let i = 0; i < 8; i++) {
    const pjCand = path.join(dir, 'package.json');
    try {
      if (fs.existsSync(pjCand) && JSON.parse(fs.readFileSync(pjCand, 'utf8')).name === 'opencli-mcp') return dir;
    } catch { /* 继续上溯 */ }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return '';
}

let opencliRoot = '';
try {
  opencliRoot = findPkgRoot(fileURLToPath(import.meta.resolve('opencli-mcp/adapter-sdk')));
} catch { /* 依赖缺失，走全局回退 */ }
if (!opencliRoot) {
  const roots = [];
  try { roots.push(spawnSync('npm', ['root', '-g'], { encoding: 'utf8' }).stdout.trim()); } catch { /* 忽略 */ }
  // nvm 常见位（当前 node 非 nvm 默认版时 npm root -g 会指错，补扫）
  try {
    const nvmDir = path.join(os.homedir(), '.nvm', 'versions', 'node');
    if (fs.existsSync(nvmDir)) {
      for (const v of fs.readdirSync(nvmDir)) roots.push(path.join(nvmDir, v, 'lib', 'node_modules'));
    }
  } catch { /* 忽略 */ }
  roots.push('/usr/local/lib/node_modules', '/opt/homebrew/lib/node_modules');
  for (const r of roots) {
    if (!r) continue;
    const cand = path.join(r, 'opencli-mcp');
    if (fs.existsSync(path.join(cand, 'package.json'))) { opencliRoot = cand; break; }
  }
}
if (!opencliRoot) die('未找到 opencli-mcp（依赖缺失）。请重装：npm install caishi-mcp');
let opencliBin;
try {
  const pj = JSON.parse(fs.readFileSync(path.join(opencliRoot, 'package.json'), 'utf8'));
  opencliBin = path.join(opencliRoot, pj.bin && typeof pj.bin === 'object' ? pj.bin['opencli-mcp'] : pj.bin);
} catch {
  die('opencli-mcp 包信息读取失败');
}
if (!fs.existsSync(opencliBin)) die('opencli-mcp 入口文件不存在: ' + opencliBin);

// —— 子命令直通：`npx caishi-mcp setup` 等直接交给 opencli-mcp ——
const passthrough = process.argv.slice(2);
if (passthrough.length > 0 && passthrough[0] !== 'stdio') {
  const r = spawnSync(process.execPath, [opencliBin, ...passthrough], { stdio: 'inherit' });
  process.exit(r.status === null ? 1 : r.status);
}

// —— 桥就绪预检（不致命；提示走 setup 的两种常态） ——
try {
  const chk = spawnSync(process.execPath, [opencliBin, 'doctor'], { encoding: 'utf8', timeout: 8000 });
  const out = String(chk.stdout || '') + String(chk.stderr || '');
  if (!/Browser connection is ready|ready/i.test(out)) {
    console.error('[caishi-mcp] 浏览器桥未就绪。请在终端运行一次：\n  npx caishi-mcp setup\n（会引导安装 Chrome 扩展并连接；仅需一次）');
  }
} catch { /* 预检失败不阻断起服 */ }

// —— 原样代理 opencli-mcp stdio ——
const child = spawn(process.execPath, [opencliBin, 'stdio'], { stdio: 'inherit' });
child.on('exit', (code, signal) => process.exit(signal ? 1 : (code === null ? 1 : code)));
child.on('error', (e) => die('拉起 opencli-mcp 失败: ' + e.message));

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => { try { child.kill(sig); } catch { /* 已退出 */ } });
}
