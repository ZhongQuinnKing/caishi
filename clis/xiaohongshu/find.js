/**
 * Xiaohongshu find — 精简版搜索（本包自研，2026-10-07）。
 *
 * 存在原因：官方 search 命令会先点"筛选面板"再取结果，而当前页面版式下
 * 筛选标签出现重复文本 → 官方报 ambiguous_option 连挂（10-07 实测 3/3）。
 * 本命令跳过筛选环节：直接导航到搜索结果页，按官方同款选择器抓卡即可。
 *
 * 边界：只支持默认排序（综合）；需要排序/类型筛选时用官方 search（修好后）。
 * 登录：复用浏览器里已登录的小红书会话。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';

function noteIdToDate(url) {
    const m = String(url || '').match(/\/(?:search_result|explore|note|discovery\/item)\/([0-9a-f]{24})/i);
    if (!m) return '';
    const ts = parseInt(m[1].slice(0, 8), 16);
    if (!Number.isFinite(ts) || ts < 1000000000) return '';
    try { return new Date(ts * 1000).toISOString().slice(0, 10); } catch { return ''; }
}

const WAIT_AND_EXTRACT_JS = (timeoutMs) => `
  new Promise((resolve) => {
    const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const collect = () => {
      const cards = [];
      const nodes = document.querySelectorAll('section.note-item, section:has(a[href*="/search_result/"]), section:has(a[href*="/explore/"])');
      for (const el of nodes) {
        if (el.classList && el.classList.contains('query-note-item')) continue;
        const r = el.getBoundingClientRect();
        if (!(r.width > 0 && r.height > 0)) continue;
        const titleEl = el.querySelector('.title, .note-title, a.title, .footer .title span');
        const nameEl = el.querySelector('a.author .name, .author-name, .nick-name, .name');
        const likesEl = el.querySelector('.count, .like-count, .like-wrapper .count');
        const linkEl = el.querySelector('a.cover.mask') || el.querySelector('a[href*="/search_result/"]') || el.querySelector('a[href*="/explore/"]') || el.querySelector('a[href*="/note/"]');
        if (!linkEl) continue;
        let href = linkEl.getAttribute('href') || '';
        if (href.startsWith('/')) href = 'https://www.xiaohongshu.com' + href;
        let title = clean(titleEl && titleEl.textContent);
        if (!title) { const sp = linkEl.querySelector('span'); title = clean(sp && sp.textContent); }
        cards.push({ href, title, author: clean(nameEl && nameEl.textContent), likes: clean(likesEl && likesEl.textContent) || '0' });
      }
      return cards;
    };
    const state = () => {
      const cards = collect();
      if (cards.length > 0) return { state: 'ok', cards };
      const t = (document.body && document.body.innerText) || '';
      if (/登录后查看|请先登录|登录后推荐更懂你/.test(t) || document.querySelector('#login-btn, [class*="login-container"]')) return { state: 'login_wall' };
      if (/没有找到|暂无|无相关结果/.test(t)) return { state: 'empty' };
      return null;
    };
    const found = state();
    if (found) return resolve(found);
    const obs = new MutationObserver(() => { const s = state(); if (s) { obs.disconnect(); resolve(s); } });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { obs.disconnect(); resolve(state() || { state: 'timeout' }); }, ${timeoutMs});
  })
`;

cli({
    site: 'xiaohongshu',
    name: 'find',
    access: 'read',
    description: '小红书精简搜索（跳过筛选面板，绕开官方 ambiguous_option bug；默认综合排序）',
    domain: 'www.xiaohongshu.com',
    strategy: Strategy.COOKIE,
    browser: true,
    example: 'opencli xiaohongshu find "钢琴教学" --limit 5 -f yaml',
    args: [
        { name: 'query', required: true, positional: true, help: '搜索关键词' },
        { name: 'limit', type: 'int', default: 10, help: '结果数量 (1-30)' },
    ],
    columns: ['rank', 'title', 'author', 'likes', 'published_at', 'url'],
    func: async (page, kwargs) => {
        const keyword = String(kwargs.query ?? '').trim();
        if (!keyword) throw new ArgumentError('xiaohongshu find 需要 <关键词>');
        const limit = Math.min(30, Math.max(1, Number(kwargs.limit) || 10));
        const url = `https://www.xiaohongshu.com/search_result?keyword=${encodeURIComponent(keyword)}&source=web_search_result_notes`;
        await page.goto(url);
        let result;
        try { result = await page.evaluate(WAIT_AND_EXTRACT_JS(12000)); }
        catch (e) { throw new CommandExecutionError(`小红书 find 提取失败: ${e instanceof Error ? e.message : String(e)}`); }
        if (result && !Array.isArray(result) && typeof result === 'object' && 'session' in result && 'data' in result) result = result.data;
        if (!result || typeof result !== 'object') throw new CommandExecutionError('小红书 find: 页面返回异常');
        if (result.state === 'login_wall') throw new AuthRequiredError('www.xiaohongshu.com', '小红书登录墙：请在浏览器里登录 xiaohongshu.com（会话短命，浏览器别关）');
        if (result.state === 'empty') throw new EmptyResultError('xiaohongshu find', `没有找到「${keyword}」的结果`);
        if (result.state === 'timeout') throw new CommandExecutionError('小红书 find 页面超时未渲染结果卡片（可能风控或网络慢，重试一次）');
        const seen = new Set();
        const rows = [];
        for (const c of (result.cards || [])) {
            if (!c.href || seen.has(c.href)) continue;
            seen.add(c.href);
            rows.push({ rank: rows.length + 1, title: c.title, author: c.author, likes: c.likes, published_at: noteIdToDate(c.href), url: c.href });
            if (rows.length >= limit) break;
        }
        if (rows.length === 0) throw new EmptyResultError('xiaohongshu find', `没有可用于「${keyword}」的结果行`);
        return rows;
    },
});
