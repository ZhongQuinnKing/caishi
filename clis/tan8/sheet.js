/**
 * 弹琴吧 sheet — 曲谱页信息 + 预览图清单（本包自研，2026-10-07）。
 *
 * 输入：弹琴吧曲谱/合集页链接（从 tan8 search 拿）。
 * 输出：曲名 + 每版谱的预览缩略图链接。
 *
 * 边界（诚实标注）：预览图是公开面；完整谱/下载在站点的会员闸口内，
 * 本命令只报公开可见的，不做任何绕过。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';

const WAIT_JS = `
  new Promise((resolve) => {
    const grab = () => {
      const title = (document.title || '').split('-')[0].trim();
      const imgs = [];
      for (const img of document.querySelectorAll('img')) {
        const s = img.getAttribute('src') || '';
        if (s.includes('yuepuku') && s.includes('_prev.jpg') && !imgs.includes(s)) imgs.push(s.startsWith('//') ? 'https:' + s : s);
      }
      if (imgs.length === 0) return null;
      return { title, imgs };
    };
    const found = grab();
    if (found) return resolve({ state: 'ok', data: found });
    const obs = new MutationObserver(() => { const f = grab(); if (f) { obs.disconnect(); resolve({ state: 'ok', data: f }); } });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => { obs.disconnect(); const f = grab(); resolve(f ? { state: 'ok', data: f } : { state: 'timeout' }); }, 10000);
  })
`;

cli({
    site: 'tan8',
    name: 'sheet',
    access: 'read',
    description: '弹琴吧曲谱页：曲名 + 各版本预览图清单（完整谱在站点）',
    domain: 'www.tan8.com',
    strategy: Strategy.PUBLIC,
    browser: true,
    example: 'opencli tan8 sheet "https://www.tan8.com/album-56071.html" -f yaml',
    args: [
        { name: 'url', required: true, positional: true, help: '弹琴吧曲谱/合集页链接' },
    ],
    columns: ['rank', 'preview', 'note'],
    func: async (page, kwargs) => {
        const url = String(kwargs.url ?? '').trim();
        if (!url) throw new ArgumentError('tan8 sheet 需要 <曲谱页链接>');
        if (!/tan8\.com\//.test(url)) throw new ArgumentError('请给弹琴吧的页面链接（tan8.com）');
        await page.goto(url);
        let r;
        try { r = await page.evaluate(WAIT_JS); }
        catch (e) { throw new CommandExecutionError(`弹琴吧曲谱页提取失败: ${e instanceof Error ? e.message : String(e)}`); }
        if (r && !Array.isArray(r) && typeof r === 'object' && 'session' in r && 'data' in r) r = r.data;
        if (!r || r.state !== 'ok') throw new CommandExecutionError('曲谱页超时未渲染（重试一次）');
        const imgs = r.data.imgs || [];
        if (imgs.length === 0) throw new EmptyResultError('tan8 sheet', '这个页面没有公开的预览图');
        return imgs.map((u, i) => ({
            rank: i + 1,
            piece: r.data.title,
            preview: u,
            note: '预览图；完整谱请到弹琴吧站点/App 查看',
        }));
    },
});
