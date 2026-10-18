// 采诗 · douyin/detail — 单条视频全解（短链/链接/ID → 文案、互动、作者、下载地址、图集）
// 移植自抖音技能/douyin-detail.js（2026-10-06 建）＋命令行版；关键设计保留：
// 详情接口必须在已登录页上下文里 fetch（同源自动附签），Node 直连会被风控。
import { defineAdapter } from '../../lib/adapter-sdk.mjs';

function extractVideoId(text) {
  if (!text) return '';
  const s = String(text).trim();
  if (/^\d{10,}$/.test(s)) return s;
  const m = s.match(/(?:douyin\.com\/video\/|iesdouyin\.com\/share\/video\/|modal_id=)(\d{10,})/);
  return m ? m[1] : '';
}

async function resolveToId(input, tab) {
  let id = extractVideoId(input);
  if (id) return id;
  if (!/^https?:\/\//.test(input)) return '';
  // 短链：让浏览器跟随重定向解析（与 bilibili 适配器同法；Node 直连拿不到 302 链）
  await tab.goto(input, { waitUntil: 'none', settleMs: 2500 });
  id = extractVideoId(String(await tab.url())) || '';
  if (!id) {
    // 兜底：分享页把 id 放在页内（aweme_id / modal_id）
    try {
      const html = await tab.evaluate('document.documentElement.innerHTML.slice(0, 200000)');
      const m = String(html || '').match(/"aweme_id"\s*[:=]\s*"?(\d{10,})/) ||
                String(html || '').match(/modal_id=(\d{10,})/);
      if (m) id = m[1];
    } catch { /* 兜底失败不致命 */ }
  }
  return id;
}

function fmtTime(ts) {
  if (!ts) return '';
  try { return new Date(ts * 1000).toISOString().slice(0, 19).replace('T', ' '); } catch { return String(ts); }
}

export default defineAdapter({
  description: 'Get a Douyin video/post in full: caption, engagement stats, author, no-watermark play address, image gallery (for 图文 posts). Accepts share short link, video URL, or numeric id.',
  access: 'read',
  domain: 'www.douyin.com',
  result: { kind: 'value', description: 'Douyin aweme detail' },
  args: [
    { name: 'target', type: 'string', required: true, help: '分享短链 / 视频链接 / 纯数字 ID' },
  ],
  run: async ({ tab, args }) => {
    const target = String(args.target || '').trim();
    if (!target) throw new Error('需要 <分享短链/链接/ID>');
    const id = await resolveToId(target, tab);
    if (!id) throw new Error('没能从输入里解析出视频 ID（若为抖音分享链，请给视频的分享链；主页/直播类短链不含视频 ID）: ' + target);
    await tab.goto('https://www.douyin.com/video/' + id, { waitUntil: 'none', settleMs: 2500 });
    const url = 'https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=' + id + '&aid=6383';
    const js = `
    (async () => {
      try {
        const res = await fetch(${JSON.stringify(url)}, { credentials: 'include', headers: { referer: 'https://www.douyin.com/' } });
        const text = await res.text();
        if (!text.trim()) return JSON.stringify({ __http: res.status, __empty: true });
        try { return JSON.stringify(JSON.parse(text)); } catch (e) { return JSON.stringify({ __http: res.status, __parsefail: text.slice(0, 300) }); }
      } catch (e) { return JSON.stringify({ __netfail: String(e && e.message || e) }); }
    })()
    `;
    const rawOut = await tab.evaluate(js);
    let raw = rawOut;
    if (typeof rawOut === 'string') { try { raw = JSON.parse(rawOut); } catch (e) { raw = null; } }
    if (raw && !Array.isArray(raw) && typeof raw === 'object' && 'session' in raw && 'data' in raw) raw = raw.data;
    if (!raw || typeof raw !== 'object') return { ok: false, aweme_id: id, reason: 'bad_response', help: '详情接口空响应或无法解析' };
    if (raw.__netfail) return { ok: false, aweme_id: id, reason: 'network_fail', help: raw.__netfail };
    if (raw.__empty) return { ok: false, aweme_id: id, reason: 'empty', help: 'HTTP ' + raw.__http };
    if (raw.__parsefail) return { ok: false, aweme_id: id, reason: 'parse_fail', help: String(raw.__parsefail).slice(0, 200) };
    if (typeof raw.status_code === 'number' && raw.status_code !== 0) {
      return { ok: false, aweme_id: id, reason: 'api_error', status_code: raw.status_code, help: String(raw.status_msg || '').slice(0, 200) };
    }
    const d = raw.aweme_detail;
    if (!d) return { ok: false, aweme_id: id, reason: 'not_found', help: '未返回详情（可能已删除或受限；登录态不足时也会至此）' };
    const st = d.statistics || {};
    return {
      ok: true,
      aweme_id: id,
      desc: d.desc ?? '',
      author: d.author?.nickname ?? '',
      author_sec_uid: d.author?.sec_uid ?? '',
      digg: st.digg_count ?? 0,
      comment: st.comment_count ?? 0,
      collect: st.collect_count ?? 0,
      share: st.share_count ?? 0,
      created: fmtTime(d.create_time),
      duration_s: Math.round((d.video?.duration ?? 0) / 1000),
      music: d.music?.title ?? '',
      play_url: d.video?.play_addr?.url_list?.[0] ?? '',
      cover: d.video?.cover?.url_list?.[0] ?? '',
      images: (d.images ?? []).map((im) => im?.url_list?.[0] ?? '').filter(Boolean),
      share_url: d.share_url ?? '',
    };
  },
});
