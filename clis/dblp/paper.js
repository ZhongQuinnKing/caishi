/**
 * dblp paper — 单篇论文记录（浏览器版，过 Anubis 盾；本包自研，2026-10-07）。
 * 输入：dblp 规范 key（如 conf/nips/VaswaniSPUJGKP17）或其页面 URL。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, EmptyResultError } from '@jackwener/opencli/errors';
import { fetchTextViaBrowser } from './_anubis.js';

cli({
    site: 'dblp',
    name: 'paper',
    access: 'read',
    description: 'dblp 单篇论文记录·浏览器版（自动过 Anubis 盾）',
    domain: 'dblp.org',
    strategy: Strategy.PUBLIC,
    browser: true,
    example: 'opencli dblp paper conf/nips/VaswaniSPUJGKP17 -f yaml',
    args: [
        { name: 'key', required: true, positional: true, help: 'dblp key 或其 rec 页面 URL' },
    ],
    columns: ['title', 'authors', 'venue', 'year', 'doi', 'url'],
    func: async (page, kwargs) => {
        let key = String(kwargs.key ?? '').trim();
        if (!key) throw new ArgumentError('dblp paper 需要 <key 或 URL>');
        const m = key.match(/dblp\.org\/rec\/(.+?)(\.html|\.xml|\.bib|\.json)?$/);
        if (m) key = m[1];
        const xml = await fetchTextViaBrowser(page, `https://dblp.org/rec/${key}.xml`, '<');
        const tag = (t) => {
            const mm = xml.match(new RegExp(`<${t}[^>]*>([\\s\\S]*?)</${t}>`, 'i'));
            return mm ? mm[1].replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').trim() : '';
        };
        const title = tag('title');
        if (!title) throw new EmptyResultError('dblp paper', `dblp 没有找到记录「${key}」（确认 key，如 conf/nips/VaswaniSPUJGKP17）`);
        const authors = [...xml.matchAll(/<author[^>]*>([\s\S]*?)<\/author>/gi)]
            .map((x) => x[1].replace(/<[^>]+>/g, '').trim()).filter(Boolean).join(', ');
        return [{
            title,
            authors: authors.slice(0, 120),
            venue: tag('venue'),
            year: tag('year'),
            doi: tag('doi'),
            url: tag('ee') || `https://dblp.org/rec/${key}.html`,
        }];
    },
});
