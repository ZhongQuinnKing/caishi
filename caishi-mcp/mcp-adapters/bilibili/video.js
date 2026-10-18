// 采诗 · bilibili/video — 视频元数据（标题/UP主/时长/统计/简介/分P）
// 移植自 opencli 命令行版 clis/bilibili/video.js（apiget 口径）；页内取数，不直连。
import { defineAdapter } from '../../lib/adapter-sdk.mjs';

function extractBvid(text) {
  if (!text) return '';
  const s = String(text).trim();
  if (/^BV[0-9A-Za-z]{10}$/.test(s)) return s;
  const m = s.match(/(BV[0-9A-Za-z]{10})/);
  return m ? m[1] : '';
}

export default defineAdapter({
  description: 'Get Bilibili video metadata (title, author, duration, stats, description) by BV id, video URL or b23.tv short link.',
  access: 'read',
  domain: 'www.bilibili.com',
  result: { kind: 'value', description: 'Bilibili video metadata' },
  args: [
    { name: 'bvid', type: 'string', required: true, help: 'BV id、视频链接或 b23.tv 短链' },
    { name: 'page', type: 'int', help: '分P 序号（从 1 起）；缺省取 P1', min: 1 },
  ],
  run: async ({ tab, args }) => {
    let bvid = extractBvid(args.bvid);
    // 短链/未知 → 让浏览器跟随重定向解析
    if (!bvid) {
      const input = String(args.bvid || '').trim();
      if (!/^https?:\/\//.test(input)) throw new Error('无法从输入解析 BV 号（给 BV id 或视频链接）');
      await tab.goto(input, { waitUntil: 'none', settleMs: 500 });
      bvid = extractBvid(String(await tab.url())) || '';
    }
    if (!bvid) throw new Error('未能从链接解析出 BV 号');
    // 页内上下文取数（带该站 cookie；API 为公开端点）
    await tab.goto('https://www.bilibili.com/video/' + bvid + '/', { waitUntil: 'none', settleMs: 800 });
    const payload = await tab.fetchJson('https://api.bilibili.com/x/web-interface/view?bvid=' + bvid);
    if (!payload || payload.code !== 0 || !payload.data) {
      return { ok: false, bvid, error: '接口返回异常 code=' + (payload && payload.code) + '（可能风控或未登录）' };
    }
    const d = payload.data;
    const pno = Math.max(1, Number(args.page) || 1);
    const part = Array.isArray(d.pages) ? d.pages[pno - 1] : undefined;
    return {
      ok: true,
      bvid,
      title: part && pno > 1 ? part.part : d.title,
      author: d.owner && d.owner.name,
      author_mid: d.owner && d.owner.mid,
      duration_s: (part && part.duration) || d.duration,
      pages: Array.isArray(d.pages) ? d.pages.length : 1,
      stats: { view: d.stat && d.stat.view, like: d.stat && d.stat.like, coin: d.stat && d.stat.coin, favorite: d.stat && d.stat.favorite, reply: d.stat && d.stat.reply, danmaku: d.stat && d.stat.danmaku },
      pubdate: d.pubdate,
      desc: String(d.desc || '').slice(0, 2000),
      url: 'https://www.bilibili.com/video/' + bvid,
    };
  },
});
