// 采诗 · xiaohongshu/note — 笔记正文与互动数据（DOM 提取）
// 移植自 opencli 命令行版 clis/xiaohongshu/note.js（NOTE_EXTRACT_JS 原样内嵌；
// 风险旗标如实结构化返回，不硬编）。建议传带 xsec_token 的完整笔记链接。
import { defineAdapter } from '../../lib/adapter-sdk.mjs';

const NOTE_EXTRACT_JS = `
(() => {
  const bodyText = document.body?.innerText || ''
  const loginWall = /登录后查看|请登录/.test(bodyText)
  const notFound = /页面不见了|笔记不存在|无法浏览/.test(bodyText)
  const securityBlock = /安全限制|访问链接异常/.test(bodyText)
    || /website-login\\/error|error_code=300017|error_code=300031/.test(location.href)
  const clean = (el) => (el?.textContent || '').replace(/\\s+/g, ' ').trim()
  const scope = document.querySelector('#noteContainer')
  const title = scope ? clean(scope.querySelector('#detail-title, .title')) : clean(document.querySelector('#detail-title'))
  const desc = scope ? clean(scope.querySelector('#detail-desc, .desc, .note-text')) : clean(document.querySelector('#detail-desc, .note-text'))
  const author = scope ? clean(scope.querySelector('.username, .author-wrapper .name')) : clean(document.querySelector('.username, .author-wrapper .name'))
  const likes = clean(document.querySelector('.interact-container .like-wrapper .count'))
  const collects = clean(document.querySelector('.interact-container .collect-wrapper .count'))
  const comments = clean(document.querySelector('.interact-container .chat-wrapper .count'))
  const tags = []
  document.querySelectorAll('#detail-desc a.tag, #detail-desc a[href*="search_result"]').forEach(el => {
    const t = (el.textContent || '').trim()
    if (t) tags.push(t)
  })
  return JSON.stringify({ pageUrl: location.href, securityBlock, loginWall, notFound, title, desc, author, likes, collects, comments, tags })
})()
`;

function parseNoteId(input) {
  const s = String(input || '').trim();
  let m = s.match(/(?:explore|discovery\/item)\/([0-9a-fA-F]{24})/);
  if (m) return m[1];
  if (/^[0-9a-fA-F]{24}$/.test(s)) return s;
  return '';
}

export default defineAdapter({
  description: 'Read a Xiaohongshu (Little Red Book) note: title, author, full text, likes/collects/comments, tags. Pass a full note URL (with xsec_token) when possible.',
  access: 'read',
  domain: 'www.xiaohongshu.com',
  result: { kind: 'value', description: 'Xiaohongshu note content and metrics' },
  args: [
    { name: 'url', type: 'string', required: true, help: '完整笔记链接（优先，含 xsec_token）或 24 位笔记 ID' },
  ],
  run: async ({ tab, args }) => {
    const raw = String(args.url || '').trim();
    const noteId = parseNoteId(raw);
    const url = /^https?:\/\//.test(raw) ? raw : (noteId ? 'https://www.xiaohongshu.com/explore/' + noteId : '');
    if (!url) throw new Error('无法解析笔记链接（给完整链接或 24 位笔记 ID）');
    await tab.goto(url, { waitUntil: 'none', settleMs: 2500 });
    const rawOut = await tab.evaluate(NOTE_EXTRACT_JS);
    let d = {};
    try { d = typeof rawOut === 'string' ? JSON.parse(rawOut) : (rawOut || {}); } catch (e) { d = {}; }
    const numOrZero = (v) => (/^\d+/.test(v || '') ? v : '0');
    if (d.loginWall) return { ok: false, note_id: noteId || null, reason: 'login_required', help: '需在同一浏览器登录小红书一次后重试' };
    if (d.notFound) return { ok: false, note_id: noteId || null, reason: 'not_found', help: '笔记不存在或已删除/受限' };
    if (d.securityBlock) return { ok: false, note_id: noteId || null, reason: 'security_block', help: '页面被风控暂时拦下，稍后重试或换带 xsec_token 的链接' };
    if (!d.title && !d.author) return { ok: false, note_id: noteId || null, reason: 'empty_render', help: '页面未渲染出内容（可能已删除/受限/需登录）' };
    return {
      ok: true,
      note_id: noteId || null,
      title: d.title || '',
      author: d.author || '',
      content: d.desc || '',
      likes: numOrZero(d.likes),
      collects: numOrZero(d.collects),
      comments: numOrZero(d.comments),
      tags: Array.isArray(d.tags) ? d.tags : [],
      page_url: d.pageUrl || url,
    };
  },
});
