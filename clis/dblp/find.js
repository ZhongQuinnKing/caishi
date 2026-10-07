/**
 * dblp find — 浏览器版 dblp 搜索（本包自研，2026-10-07）。
 *
 * 存在原因：dblp.org 上了 Anubis 防机器人盾（官方无头请求会拿到
 * "Making sure you're not a bot!" 挑战页 → JSON 解析失败）。真浏览器
 * 能自动过盾（PoW 几秒），所以本命令走浏览器桥：直接导航到 API 地址，
 * 盾过完页面体就是 JSON，读出来即可。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';

cli({
    site: 'dblp',
    name: 'find',
    access: 'read',
    description: 'dblp 论文搜索·浏览器版（自动过 Anubis 盾；官方 search 因该盾失效时用这条）',
    domain: 'dblp.org',
    strategy: Strategy.PUBLIC,
    browser: true,
    example: 'opencli dblp find "attention is all you need" --limit 5 -f yaml',
    args: [
        { name: 'query', required: true, positional: true, help: '关键词（标题/作者/会议）' },
        { name: 'limit', type: 'int', default: 10, help: '结果数量 (1-30)' },
    ],
    columns: ['rank', 'title', 'authors', 'venue', 'year', 'url'],
    func: async (page, kwargs) => {
        const q = String(kwargs.query ?? '').trim();
        if (!q) throw new ArgumentError('dblp find 需要 <关键词>');
        const limit = Math.min(30, Math.max(1, Number(kwargs.limit) || 10));
        const api = `https://dblp.org/search/publ/api?q=${encodeURIComponent(q)}&format=json&h=${limit}`;
        await page.goto(api);
        // Anubis 盾需要几秒 PoW；轮询等页面体变成 JSON
        let data = null;
        for (let i = 0; i < 20; i++) {
            await page.wait(2);
            let body = '';
            try { body = await page.evaluate("() => document.body ? document.body.innerText : ''"); } catch { continue; }
            if (body && body.trim().startsWith('{')) {
                try { data = JSON.parse(body); break; } catch { /* 还没完 */ }
            }
        }
        if (!data) throw new CommandExecutionError('dblp：Anubis 盾未过或响应超时（重试一次）');
        const hits = data?.result?.hits?.hit || [];
        if (hits.length === 0) throw new EmptyResultError('dblp find', `dblp 没有找到「${q}」`);
        return hits.slice(0, limit).map((h, i) => {
            const info = h.info || {};
            const authors = Array.isArray(info.authors?.author)
                ? info.authors.author.map((a) => a.text || a).join(', ')
                : String(info.authors?.author?.text || '');
            return {
                rank: i + 1,
                title: String(info.title || '').replace(/&apos;/g, "'").replace(/&amp;/g, '&'),
                authors: authors.slice(0, 90),
                venue: info.venue || '',
                year: info.year || '',
                url: info.ee || info.url || '',
            };
        });
    },
});
