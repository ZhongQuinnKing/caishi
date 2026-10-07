/**
 * dblp venue — 会议/期刊检索（浏览器版，过 Anubis 盾；本包自研，2026-10-07）。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, EmptyResultError } from '@jackwener/opencli/errors';
import { fetchJsonViaBrowser, hitsOf } from './_anubis.js';

cli({
    site: 'dblp',
    name: 'venue',
    access: 'read',
    description: 'dblp 会议/期刊检索·浏览器版（自动过 Anubis 盾）',
    domain: 'dblp.org',
    strategy: Strategy.PUBLIC,
    browser: true,
    example: 'opencli dblp venue "NeurIPS" --limit 5 -f yaml',
    args: [
        { name: 'query', required: true, positional: true, help: '会议/期刊名（如 NeurIPS）' },
        { name: 'limit', type: 'int', default: 10, help: '结果数量 (1-30)' },
    ],
    columns: ['rank', 'venue', 'acronym', 'url'],
    func: async (page, kwargs) => {
        const q = String(kwargs.query ?? '').trim();
        if (!q) throw new ArgumentError('dblp venue 需要 <会议/期刊名>');
        const limit = Math.min(30, Math.max(1, Number(kwargs.limit) || 10));
        const data = await fetchJsonViaBrowser(page, `https://dblp.org/search/venue/api?q=${encodeURIComponent(q)}&format=json&h=${limit}`);
        const hits = hitsOf(data);
        if (hits.length === 0) throw new EmptyResultError('dblp venue', `dblp 没有找到「${q}」`);
        return hits.slice(0, limit).map((h, i) => {
            const info = h.info || {};
            return { rank: i + 1, venue: info.venue || '', acronym: info.acronym || '', url: info.url || '' };
        });
    },
});
