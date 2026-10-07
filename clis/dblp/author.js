/**
 * dblp author — 作者搜索（浏览器版，过 Anubis 盾；本包自研，2026-10-07）。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, EmptyResultError } from '@jackwener/opencli/errors';
import { fetchJsonViaBrowser, hitsOf } from './_anubis.js';

cli({
    site: 'dblp',
    name: 'author',
    access: 'read',
    description: 'dblp 作者搜索·浏览器版（自动过 Anubis 盾）',
    domain: 'dblp.org',
    strategy: Strategy.PUBLIC,
    browser: true,
    example: 'opencli dblp author "Yoshua Bengio" --limit 5 -f yaml',
    args: [
        { name: 'query', required: true, positional: true, help: '作者名' },
        { name: 'limit', type: 'int', default: 10, help: '结果数量 (1-30)' },
    ],
    columns: ['rank', 'name', 'notes', 'url'],
    func: async (page, kwargs) => {
        const q = String(kwargs.query ?? '').trim();
        if (!q) throw new ArgumentError('dblp author 需要 <作者名>');
        const limit = Math.min(30, Math.max(1, Number(kwargs.limit) || 10));
        const data = await fetchJsonViaBrowser(page, `https://dblp.org/search/author/api?q=${encodeURIComponent(q)}&format=json&h=${limit}`);
        const hits = hitsOf(data);
        if (hits.length === 0) throw new EmptyResultError('dblp author', `dblp 没有找到作者「${q}」`);
        return hits.slice(0, limit).map((h, i) => {
            const info = h.info || {};
            let notes = info.notes?.note;
            if (Array.isArray(notes)) notes = notes.map((x) => (typeof x === 'object' ? x.text || '' : x)).join(' / ');
            else if (notes && typeof notes === 'object') notes = notes.text || '';
            return { rank: i + 1, name: info.author || '', notes: String(notes || '').slice(0, 80), url: info.url || '' };
        });
    },
});
