/**
 * 弹琴吧 search — 搜曲（本包自研，2026-10-07；2026-10-09 修复选择器）。
 *
 * 弹琴吧（tan8.com）= 国内流行曲谱站（钢琴/吉他）。结果页是 JS 渲染，
 * 所以本命令走浏览器桥抓渲染后的卡片。
 *
 * 2026-10-09 修复记录：站点结果列表真实结构为
 *   ul[class*="yuepuClassify_list"] > li > a[href*="yuepu-"]，
 * 旧选择器（.musicImgCon / a[href*="album-"]）在现行页面永不命中，
 * 表现为固定超时后报「搜索页超时未渲染」——实为选择器过时，不是渲染问题。
 * 现以新选择器为主、旧结构兜底；并把上传者/页数一并抓出来。
 *
 * 边界（诚实标注）：公开面只有"搜曲 + 预览图 + 跳转链接"；
 * 完整谱是站点的会员/登录闸口 —— 本命令绝不触碰付费内容。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';

const WAIT_JS = `
  new Promise((resolve) => {
    const grab = () => {
      const rows = []; const seen = new Set();
      const push = (a, container) => {
        const href = a.getAttribute('href') || '';
        if (!/yuepu-/.test(href) || seen.has(href)) return;
        seen.add(href);
        const lines = ((container.innerText || '').split('\\n')).map(s => s.trim()).filter(Boolean);
        const title = (lines[0] || '').replace(/^\\d+[.、]\\s*/, '') || href;
        const artist = lines[1] || '';
        const uploader = (lines.find(s => s.includes('上传')) || '').replace(/^上传[：:]\\s*/, '');
        const pages = (lines.find(s => /^\\d+\\s*页$/.test(s)) || '').replace(/\\s/g, '');
        rows.push({ title, artist, uploader, pages, url: 'https://www.tan8.com' + href });
      };
      for (const li of document.querySelectorAll('ul[class*="yuepuClassify_list"] > li, ul[class*="yuepuClassify"] > li')) {
        const a = li.querySelector('a[href*="yuepu-"]');
        if (a) push(a, li);
      }
      if (rows.length === 0) {
        for (const el of document.querySelectorAll('.musicImgCon, [class*="musicImg"]')) {
          const a = el.querySelector('a[href*="yuepu-"], a[href*="album-"]');
          if (a) push(a, el);
        }
      }
      return rows;
    };
    const found = grab();
    if (found.length > 0) return resolve({ state: 'ok', rows: found });
    const obs = new MutationObserver(() => { const r = grab(); if (r.length > 0) { obs.disconnect(); resolve({ state: 'ok', rows: r }); } });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { obs.disconnect(); const r = grab(); resolve(r.length ? { state: 'ok', rows: r } : { state: 'timeout' }); }, 12000);
  })
`;

cli({
    site: 'tan8',
    name: 'search',
    access: 'read',
    description: '弹琴吧搜曲（流行曲谱：曲名/艺人/上传者/页数/链接；完整谱在站点）',
    domain: 'www.tan8.com',
    strategy: Strategy.PUBLIC,
    browser: true,
    example: 'opencli tan8 search "梦中的婚礼" --limit 8 -f yaml',
    args: [
        { name: 'query', required: true, positional: true, help: '曲名 / 歌手' },
        { name: 'limit', type: 'int', default: 10, help: '结果数量 (1-30)' },
    ],
    columns: ['rank', 'title', 'artist', 'uploader', 'pages', 'url'],
    func: async (page, kwargs) => {
        const q = String(kwargs.query ?? '').trim();
        if (!q) throw new ArgumentError('tan8 search 需要 <曲名/歌手>');
        const limit = Math.min(30, Math.max(1, Number(kwargs.limit) || 10));
        await page.goto(`https://www.tan8.com/search-1-1-0.php?keyword=${encodeURIComponent(q)}`);
        let r;
        try { r = await page.evaluate(WAIT_JS); }
        catch (e) { throw new CommandExecutionError(`弹琴吧搜索提取失败: ${e instanceof Error ? e.message : String(e)}`); }
        if (r && !Array.isArray(r) && typeof r === 'object' && 'session' in r && 'data' in r) r = r.data;
        if (!r || r.state !== 'ok') throw new CommandExecutionError('弹琴吧搜索页超时未渲染（确认专用窗在屏幕内：dywin show）');
        if (!r.rows || r.rows.length === 0) throw new EmptyResultError('tan8 search', `弹琴吧没有找到「${q}」`);
        return r.rows.slice(0, limit).map((x, i) => ({ rank: i + 1, title: x.title, artist: x.artist, uploader: x.uploader, pages: x.pages, url: x.url }));
    },
});
