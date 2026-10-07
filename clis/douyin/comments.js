/**
 * Douyin comments — 任意视频的评论列表（本包自研，2026-10-07）。
 *
 * 官方 douyin 适配器没有独立的评论命令（只在 user-videos 里附带自己作品的
 * 热评）。本命令面向任意视频链接/ID，拿顶层评论：内容、点赞、作者、回复数。
 *
 * 机制：与 detail 相同——必须在已登录页面上下文里 fetch，抖音网页 JS 自动
 * 给同源 /aweme/ 请求加签名。接口：/aweme/v1/web/comment/list/
 */
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors';

export function extractVideoId(text) {
    if (!text) return '';
    const s = String(text).trim();
    if (/^\d{10,}$/.test(s)) return s;
    const m = s.match(/(?:douyin\.com\/video\/|iesdouyin\.com\/share\/video\/|modal_id=)(\d{10,})/);
    return m ? m[1] : '';
}

async function resolveToId(input) {
    let id = extractVideoId(input);
    if (id) return id;
    if (!/^https?:\/\//.test(input)) return '';
    let url = input;
    for (let hop = 0; hop < 6; hop++) {
        let res;
        try {
            res = await fetch(url, {
                redirect: 'manual',
                headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' },
            });
        } catch (e) { throw new CommandExecutionError(`短链解析失败: ${e instanceof Error ? e.message : String(e)}`); }
        const loc = res.headers.get('location') || '';
        id = extractVideoId(loc) || extractVideoId(res.url || '');
        if (id) return id;
        if (!loc) return '';
        url = new URL(loc, url).toString();
    }
    return '';
}

async function pageFetchJson(page, url) {
    const js = `
    (async () => {
      try {
        const res = await fetch(${JSON.stringify(url)}, { credentials: 'include', headers: { referer: 'https://www.douyin.com/' } });
        const text = await res.text();
        if (!text.trim()) return { __http: res.status, __empty: true };
        try { return JSON.parse(text); } catch (e) { return { __http: res.status, __parsefail: text.slice(0, 300) }; }
      } catch (e) { return { __netfail: String(e && e.message || e) }; }
    })()
    `;
    let raw = await page.evaluate(js);
    if (raw && !Array.isArray(raw) && typeof raw === 'object' && 'session' in raw && 'data' in raw) raw = raw.data;
    if (!raw || typeof raw !== 'object') throw new CommandExecutionError('评论接口返回异常（空响应）');
    if (raw.__netfail) throw new CommandExecutionError(`评论接口网络失败: ${raw.__netfail}`);
    if (raw.__empty) throw new CommandExecutionError(`评论接口空响应 (HTTP ${raw.__http})`);
    if (raw.__parsefail) throw new CommandExecutionError(`评论接口非 JSON: ${raw.__parsefail}`);
    if (typeof raw.status_code === 'number' && raw.status_code !== 0) {
        throw new CommandExecutionError(`评论接口错误 status_code=${raw.status_code}: ${raw.status_msg || ''}`);
    }
    return raw;
}

function fmtTime(ts) {
    if (!ts) return '';
    try { return new Date(ts * 1000).toISOString().slice(0, 16).replace('T', ' '); } catch { return String(ts); }
}

cli({
    site: 'douyin',
    name: 'comments',
    access: 'read',
    description: '任意抖音视频的评论列表（内容/点赞/作者/回复数/时间）',
    domain: 'www.douyin.com',
    strategy: Strategy.COOKIE,
    browser: true,
    example: 'opencli douyin comments "https://v.douyin.com/xxxx/" --limit 20 -f yaml',
    args: [
        { name: 'target', required: true, positional: true, help: '分享短链 / 视频链接 / 纯数字 ID' },
        { name: 'limit', type: 'int', default: 20, help: '评论数量 (1-50)' },
    ],
    columns: ['rank', 'digg', 'replies', 'author', 'text'],
    func: async (page, kwargs) => {
        const target = String(kwargs.target ?? '').trim();
        if (!target) throw new ArgumentError('douyin comments 需要 <链接/ID>');
        const limit = Math.min(50, Math.max(1, Number(kwargs.limit) || 20));
        const id = await resolveToId(target);
        if (!id) throw new ArgumentError(`没能从输入里解析出视频 ID: ${target}`);
        await page.goto(`https://www.douyin.com/video/${id}`);
        await page.wait(2);
        const params = new URLSearchParams({ aweme_id: id, cursor: '0', count: String(limit), aid: '6383' });
        const data = await pageFetchJson(page, `https://www.douyin.com/aweme/v1/web/comment/list/?${params.toString()}`);
        const list = data.comments || [];
        if (list.length === 0) throw new EmptyResultError('douyin comments', `视频 ${id} 没有取到评论（可能已关闭或受限）`);
        return list.slice(0, limit).map((c, i) => ({
            rank: i + 1,
            digg: c.digg_count ?? 0,
            replies: c.reply_comment_total ?? 0,
            author: c.user?.nickname ?? '',
            text: String(c.text || '').replace(/\s+/g, ' ').slice(0, 200),
            time: fmtTime(c.create_time),
        }));
    },
});
