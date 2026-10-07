/**
 * IMSLP files — 某作品的全部曲谱文件（本包自研，2026-10-07）。
 *
 * 输入：作品页标题（从 imslp search 拿）或完整 imslp.org/wiki/... 链接。
 * 输出：每个谱子文件的索引号、描述片段、下载页链接（Special:ImagefromIndex/<id>）。
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';
import { imslpApi } from './search.js';

cli({
    site: 'imslp',
    name: 'files',
    access: 'read',
    description: 'IMSLP 某作品的全部曲谱文件（索引号/描述/下载链接，免登录）',
    domain: 'imslp.org',
    strategy: Strategy.PUBLIC,
    browser: false,
    example: 'opencli imslp files "Piano Sonata No.14, Op.27 No.2 (Beethoven, Ludwig van)" --limit 10 -f yaml',
    args: [
        { name: 'page', required: true, positional: true, help: '作品页标题，或完整 imslp.org/wiki/... 链接' },
        { name: 'limit', type: 'int', default: 20, help: '最多返回多少个文件 (1-50)' },
    ],
    columns: ['rank', 'index', 'desc', 'url'],
    func: async (kwargs) => {
        let page = String(kwargs.page ?? '').trim();
        if (!page) throw new ArgumentError('imslp files 需要 <作品页标题或链接>');
        const limit = Math.min(50, Math.max(1, Number(kwargs.limit) || 20));
        const m = page.match(/imslp\.org\/wiki\/(.+)$/);
        if (m) page = decodeURIComponent(m[1]).replace(/_/g, ' ');
        const d = await imslpApi({ action: 'parse', page, prop: 'text', redirects: '1' });
        if (d?.error) throw new CommandExecutionError(`IMSLP: ${d.error.info || d.error.code}`);
        const t = d?.parse?.text;
        const html = typeof t === 'string' ? t : (t && (t['*'] || t.text || '')) || '';
        const out = [];
        const seen = new Set();
        const re = /Special:ImagefromIndex\/(\d+)/g;
        let mm;
        while ((mm = re.exec(html)) && out.length < limit) {
            const id = mm[1];
            if (seen.has(id)) continue;
            seen.add(id);
            const close = html.indexOf('">', mm.index);
            const seg = close > -1 ? html.slice(close + 2, close + 220) : '';
            const desc = seg
                .replace(/&#160;|&nbsp;/g, ' ')
                .replace(/<[^>]+>/g, ' ')
                .split('<')[0]
                .replace(/\s+/g, ' ')
                .trim();
            out.push({
                rank: out.length + 1,
                index: id,
                desc: desc.slice(0, 100),
                url: `https://imslp.org/wiki/Special:ImagefromIndex/${id}`,
            });
        }
        if (out.length === 0) throw new EmptyResultError('imslp files', `作品页「${page}」没有解析到曲谱文件`);
        return out;
    },
});
