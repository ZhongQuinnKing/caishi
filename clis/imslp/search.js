/**
 * IMSLP search — 全球公有领域乐谱库搜索（本包自研，2026-10-07）。
 *
 * IMSLP（imslp.org）是全世界最大的公有领域乐谱库。它没有官方 CLI，
 * 本命令用它的 MediaWiki API 做搜索；配套 `imslp files` 拿某作品的谱子文件。
 *
 * 无登录、无 cookie；直连 imslp.org API（已验证可达）。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';

const API = 'https://imslp.org/api.php';
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

export async function imslpApi(params) {
    const url = `${API}?${new URLSearchParams({ ...params, format: 'json', formatversion: '2' }).toString()}`;
    const r = await fetch(url, { headers: { 'User-Agent': UA } });
    if (!r.ok) throw new CommandExecutionError(`IMSLP API HTTP ${r.status}`);
    return r.json();
}

cli({
    site: 'imslp',
    name: 'search',
    access: 'read',
    description: 'IMSLP 乐谱库搜索（全球公有领域乐谱，免登录）',
    domain: 'imslp.org',
    strategy: Strategy.PUBLIC,
    browser: false,
    example: 'opencli imslp search "Moonlight Sonata" --limit 5 -f yaml',
    args: [
        { name: 'query', required: true, positional: true, help: '曲名 / 作曲家 / 作品号' },
        { name: 'limit', type: 'int', default: 10, help: '结果数量 (1-30)' },
    ],
    columns: ['rank', 'title', 'url'],
    func: async (kwargs) => {
        const q = String(kwargs.query ?? '').trim();
        if (!q) throw new ArgumentError('imslp search 需要 <曲名/作曲家>');
        const limit = Math.min(30, Math.max(1, Number(kwargs.limit) || 10));
        const d = await imslpApi({ action: 'query', list: 'search', srsearch: q, srlimit: String(limit), redirects: '1' });
        const hits = d?.query?.search || [];
        if (hits.length === 0) throw new EmptyResultError('imslp search', `IMSLP 没有找到「${q}」`);
        return hits.map((h, i) => ({
            rank: i + 1,
            title: h.title,
            url: 'https://imslp.org/wiki/' + encodeURIComponent(String(h.title).replace(/ /g, '_')),
        }));
    },
});
