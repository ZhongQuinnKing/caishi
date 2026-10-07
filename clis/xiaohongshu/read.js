/**
 * Xiaohongshu read — 单篇笔记全解（本包自研，2026-10-07）。
 *
 * 与官方 note 命令并存：官方版按 UI 自动化走，时好时坏（10-07 撞 SECURITY_BLOCK /
 * Navigation rejected）；本版只做"导航 + DOM 抓取"，路径更短更稳。
 *
 * 输入要求：带 xsec_token 的完整链接（从 find/搜索/分享里拿到的原始 URL）。
 * 裸 ID 不行 —— 小红书强制 xsec_token 机制。
 *
 * 登录：复用浏览器里已登录的小红书会话；会话短命，浏览器保持开着。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';

const EXTRACT_JS = (timeoutMs) => `
  new Promise((resolve) => {
    const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const grab = () => {
      const q = (sels) => { for (const s of sels) { const el = document.querySelector(s); if (el) return el; } return null; };
      const titleEl = q(['#detail-title', '.note-content .title', '.title']);
      const descEl = q(['#detail-desc', '.note-content .desc', '.desc']);
      const authorEl = q(['.author-container .username', '.author-wrapper .username', '.author-wrapper .name', '.username']);
      const dateEl = q(['.bottom-container .date', '.date']);
      const like = q(['.like-wrapper .count', '.interact-container .like-wrapper .count']);
      const collect = q(['.collect-wrapper .count', '.interact-container .collect-wrapper .count']);
      const comment = q(['.chat-wrapper .count', '.interact-container .chat-wrapper .count']);
      const imgs = [];
      for (const img of document.querySelectorAll('.swiper-slide img, #noteContainer .media-container img, .note-slider img')) {
        const s = img.getAttribute('src');
        if (s && !s.includes('avatar') && !imgs.includes(s)) imgs.push(s);
      }
      const video = document.querySelector('video');
      const title = clean(titleEl && titleEl.textContent);
      const content = clean(descEl && descEl.textContent);
      if (!title && !content) return null;
      return { title, content, author: clean(authorEl && authorEl.textContent),
               date: clean(dateEl && dateEl.textContent),
               likes: clean(like && like.textContent), collects: clean(collect && collect.textContent),
               comments_count: clean(comment && comment.textContent),
               images: imgs, has_video: !!video, url: location.href.split('?')[0] };
    };
    const wall = () => {
      const t = (document.body && document.body.innerText) || '';
      if (/登录后查看|请先登录|登录后推荐更懂你/.test(t)) return 'login_wall';
      if (/当前笔记暂时无法浏览|违规|风险/.test(t)) return 'blocked';
      return null;
    };
    const found = grab();
    if (found) return resolve({ state: 'ok', data: found });
    const w = wall();
    if (w) return resolve({ state: w });
    const obs = new MutationObserver(() => {
      const f = grab(); if (f) { obs.disconnect(); resolve({ state: 'ok', data: f }); }
      const ww = wall(); if (ww) { obs.disconnect(); resolve({ state: ww }); }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { obs.disconnect(); resolve(grab() ? { state: 'ok', data: grab() } : { state: 'timeout' }); }, ${timeoutMs});
  })
`;

cli({
    site: 'xiaohongshu',
    name: 'read',
    access: 'read',
    description: '单篇笔记全解：标题/正文/作者/互动数/日期/图集（需带 xsec_token 的完整链接）',
    domain: 'www.xiaohongshu.com',
    strategy: Strategy.COOKIE,
    browser: true,
    example: 'opencli xiaohongshu read "https://www.xiaohongshu.com/search_result/xxxx?xsec_token=..." -f yaml',
    args: [
        { name: 'url', required: true, positional: true, help: '带 xsec_token 的笔记完整链接' },
    ],
    columns: ['title', 'author', 'likes', 'collects', 'comments_count', 'date', 'images', 'content'],
    func: async (page, kwargs) => {
        const url = String(kwargs.url ?? '').trim();
        if (!url) throw new ArgumentError('xiaohongshu read 需要 <笔记链接>');
        if (!/https?:\/\/[^ ]*xiaohongshu\.com\//.test(url)) throw new ArgumentError('请给完整的小红书链接（带 xsec_token）');
        await page.goto(url);
        let r;
        try { r = await page.evaluate(EXTRACT_JS(12000)); }
        catch (e) { throw new CommandExecutionError(`小红书 read 提取失败: ${e instanceof Error ? e.message : String(e)}`); }
        if (r && !Array.isArray(r) && typeof r === 'object' && 'session' in r && 'data' in r) r = r.data;
        if (!r || typeof r !== 'object') throw new CommandExecutionError('小红书 read: 页面返回异常');
        if (r.state === 'login_wall') throw new AuthRequiredError('www.xiaohongshu.com', '小红书登录墙：在你登录小红书所用的浏览器里保持登录状态（会话短命，别关浏览器）');
        if (r.state === 'blocked') throw new CommandExecutionError('这篇笔记被小红书风控拦截（违规/风险提示页）');
        if (r.state === 'timeout') throw new CommandExecutionError('页面超时未渲染出笔记内容（可能风控或网络慢，重试一次）');
        const d = r.data;
        return [{
            title: d.title,
            author: d.author,
            likes: d.likes || '0',
            collects: d.collects || '0',
            comments_count: d.comments_count || '0',
            date: d.date,
            images: (d.images || []).length,
            first_image: (d.images || [])[0] || '',
            has_video: d.has_video,
            content: d.content,
            url: d.url,
        }];
    },
});
