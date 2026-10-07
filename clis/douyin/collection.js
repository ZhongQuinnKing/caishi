/**
 * Douyin collection — 读取一条视频所在的"合集"（系列）全部集数（本包自研，2026-10-07）。
 *
 * 场景：追系列课/连载时，给任意一集的链接 → 拿到合集名 + 全部集数列表
 * （集名/点赞/时长/链接），顺序即合集内的排期顺序。
 *
 * 机制：与 detail 相同——已登录页面上下文里 fetch（抖音网页 JS 自动加签名）。
 * 详情接口的 mix_info 给出 mix_id，再拉 /aweme/v1/web/mix/aweme/ 拿清单。
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
    if (!raw || typeof raw !== 'object') throw new CommandExecutionError('接口返回异常（空响应）');
    if (raw.__netfail) throw new CommandExecutionError(`接口网络失败: ${raw.__netfail}`);
    if (raw.__empty) throw new CommandExecutionError(`接口空响应 (HTTP ${raw.__http})`);
    if (raw.__parsefail) throw new CommandExecutionError(`接口非 JSON: ${raw.__parsefail}`);
    if (typeof raw.status_code === 'number' && raw.status_code !== 0) {
        throw new CommandExecutionError(`接口错误 status_code=${raw.status_code}: ${raw.status_msg || ''}`);
    }
    return raw;
}

cli({
    site: 'douyin',
    name: 'collection',
    access: 'read',
    description: '读取视频所在合集（系列）的全部集数：合集名 + 每集标题/点赞/时长/链接',
    domain: 'www.douyin.com',
    strategy: Strategy.COOKIE,
    browser: true,
    example: 'opencli douyin collection "https://v.douyin.com/xxxx/" -f yaml',
    args: [
        { name: 'target', required: true, positional: true, help: '合集中任意一集的链接 / ID' },
        { name: 'limit', type: 'int', default: 60, help: '最多返回多少集 (1-200)' },
    ],
    columns: ['rank', 'aweme_id', 'desc', 'digg', 'duration_s', 'url'],
    func: async (page, kwargs) => {
        const target = String(kwargs.target ?? '').trim();
        if (!target) throw new ArgumentError('douyin collection 需要 <链接/ID>');
        const limit = Math.min(200, Math.max(1, Number(kwargs.limit) || 60));
        const id = await resolveToId(target);
        if (!id) throw new ArgumentError(`没能从输入里解析出视频 ID: ${target}`);
        await page.goto(`https://www.douyin.com/video/${id}`);
        await page.wait(2);
        const detail = await pageFetchJson(page, `https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=${id}&aid=6383`);
        const mix = detail.aweme_detail?.mix_info;
        if (!mix || !mix.mix_id) {
            throw new EmptyResultError('douyin collection', `这条视频（${id}）不在任何合集里`);
        }
        const mixName = mix.mix_name || mix.mix_info?.mix_name || '(未命名合集)';
        const params = new URLSearchParams({ mix_id: String(mix.mix_id), count: String(Math.min(limit, 100)), cursor: '0', aid: '6383' });
        const data = await pageFetchJson(page, `https://www.douyin.com/aweme/v1/web/mix/aweme/?${params.toString()}`);
        const list = data.aweme_list || [];
        if (list.length === 0) throw new EmptyResultError('douyin collection', `合集「${mixName}」没有取到集数列表`);
        return list.slice(0, limit).map((a, i) => ({
            rank: i + 1,
            mix_name: mixName,
            aweme_id: a.aweme_id,
            desc: String(a.desc || '').replace(/\s+/g, ' ').slice(0, 80),
            digg: a.statistics?.digg_count ?? 0,
            duration_s: Math.round((a.video?.duration ?? 0) / 1000),
            url: `https://www.douyin.com/video/${a.aweme_id}`,
        }));
    },
});
