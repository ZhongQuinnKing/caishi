/**
 * dblp 浏览器取数公共件（本包自研，2026-10-07）。
 *
 * dblp.org 有 Anubis 防机器人盾：无头请求拿到挑战页。真浏览器能自动过盾（PoW 几秒）。
 * 稳妥姿势（实测）：
 *   1) 先访问 dblp.org 首页，等盾过完（标题出现 dblp）
 *   2) 在页面上下文里 fetch 目标接口（xml / json 都会直出，不受"下载不渲染"影响）
 *   3) 若返回像挑战页/HTML，重试
 */
import { CommandExecutionError } from '@jackwener/opencli/errors';

function looksLikeShieldOrHtml(text) {
    if (!text) return true;
    const head = text.slice(0, 200).toLowerCase();
    if (head.startsWith('<!doctype') || head.startsWith('<html')) return true;
    return /making sure you.{0,5}re not a bot/i.test(text.slice(0, 500));
}

export async function fetchViaBrowser(page, url, { asJson = false, expectPrefix = '', tries = 3 } = {}) {
    for (let t = 0; t < tries; t++) {
        await page.goto('https://dblp.org/');
        for (let i = 0; i < 15; i++) {
            await page.wait(2);
            let title = '';
            try { title = await page.evaluate('() => document.title || ""'); } catch { /* 页面切换中 */ }
            if (/dblp/i.test(title)) break;
        }
        let body = '';
        try {
            body = await page.evaluate(`async () => {
                try {
                    const res = await fetch(${JSON.stringify(url)}, { credentials: 'include' });
                    return await res.text();
                } catch (e) { return 'FETCHERR ' + String(e && e.message || e); }
            }`);
        } catch (e) {
            body = 'EVALERR ' + String(e && e.message || e);
        }
        if (body && !body.startsWith('FETCHERR') && !body.startsWith('EVALERR') &&
            !looksLikeShieldOrHtml(body) && (!expectPrefix || body.trim().startsWith(expectPrefix))) {
            try { return asJson ? JSON.parse(body) : body; }
            catch { return body; }
        }
    }
    throw new CommandExecutionError('dblp：过盾/取数失败（重试一次）');
}

export async function fetchJsonViaBrowser(page, url, tries = 3) {
    return fetchViaBrowser(page, url, { asJson: true, expectPrefix: '{', tries });
}

export async function fetchTextViaBrowser(page, url, expectPrefix = '', tries = 3) {
    return fetchViaBrowser(page, url, { expectPrefix, tries });
}

export function hitsOf(data) {
    const hit = data?.result?.hits?.hit;
    if (!hit) return [];
    return Array.isArray(hit) ? hit : [hit];
}

export function authorsText(info) {
    const a = info?.authors?.author;
    if (Array.isArray(a)) return a.map((x) => x.text || x).join(', ');
    return String(a?.text || a || '');
}
