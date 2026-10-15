Caishi: platform status (test results as the source of truth)
Repository: https://github.com/ZhongQuinnKing/caishi
Chinese version: [平台状态表.md](./平台状态表.md)（中文版）

Updated: 2026-10-07 (v0.4, two rounds of testing)
Principle: write only what has been tested; leave out what is not certain, and drop what cannot be done.


1. Field report across seven platforms

| Platform | What it reads | Login needed | Test status | Last tested |
|------|----------|----------|----------|----------------|
| Toutiao | Hot list, recommendation feed | No login | Passes (pure endpoint; not even a browser) | 2026-10-07 |
| IMSLP | Score search, all score files for a work | No login | In-house as of 10-07 (global public-domain score library; search + files, two commands; zhread wired up) | 2026-10-07 |
| Tan8 | Score search, preview image of a score page | No login | In-house as of 10-07 (search + sheet; **full scores sit behind the site's membership gate, so it reports the public face only and never bypasses it**) | 2026-10-07 |
| WeChat Official Accounts | Search (via Sogou WeChat) | No login | Passes (needs the browser bridge) | 2026-10-07 |
| WeChat Official Accounts | Full-text export to Markdown | **No login** | Verified 10-07 (clean Markdown export: title / author / time / images / full text) | 2026-10-07 |
| Bilibili | Trending, search, video detail, audio | No login | Passes | 2026-10-07 |
| Bilibili | Subtitles, official AI summary | Login required (already signed in) | Verified 10-07: subtitles carry a timeline, and the AI summary includes a segmented outline with timestamps | 2026-10-07 |
| Weibo | Hot search | No login | Passes | 2026-10-07 |
| Weibo | Feed/post reading | Login required (test account signed in) | Verified 10-07 (the feed returns real data: author / body / likes-comments-reposts / time / link) | 2026-10-07 |
| Douyin | Single-link full extract (in-house detail), search, user works | Login required | Passes (dedicated window signed in) | 2026-10-07 |
| Douyin | Comment list (in-house comments) | Login required | Passed first try on 10-07 (text / likes / author / reply count / time) | 2026-10-07 |
| Douyin | Collection/series reading (in-house collection) | Login required | Passed first try on 10-07 (give one episode, get the whole series list: "piano course collection", all 6 episodes) | 2026-10-07 |
| Xiaohongshu | Search / full note extract (both in-house) | Login required | 10-07: `xiaohongshu find` (search) and `xiaohongshu read` (full note: title / body / engagement / image set) both passed first try; the official search/note are retired (layout bugs plus risk control); **short-session pitfall: closing the browser drops the login**, so the rule is to keep the main Chrome open | 2026-10-07 |
| Zhihu | Answer and column read/export | Login required | Verified 10-07: **answers via `answer-detail`** (full body / upvotes / comments / question title), **columns via `download`** (full export); zhread wired up | 2026-10-07 |

(The "Last tested" column refreshes every Sunday; until then the previous test date stands.)


2. Conclusion

All seven main platforms test as usable: Douyin, Bilibili, Xiaohongshu, Weibo, Zhihu, WeChat Official Accounts and Toutiao.
Nine in-house pieces covering 14 commands fill the official gaps: douyin detail / comments / collection, xiaohongshu find / read, imslp search + files, tan8 search + sheet, dblp find / author / venue / paper (the browser build slips past the Anubis shield automatically), and web-page reading (web read).
Three general utilities: zhread (one command to read any link), zhcheck (platform health check), and zhupdate (update and repair).

Total: **33 sites usable right now**; plus 4 once login or permission is added (Taobao, Maimai, linux.do, CNKI); plus 3 more with a proxy (Google Scholar, Wikipedia, Hugging Face) → **40 fully loaded**.


3. How sign-in is arranged

This pack reuses the **already signed-in session** in your local browser; it copies no cookies and signs you in for nothing.
- Sign in to your regular platforms from one fixed browser environment, and do not scan repeatedly across multiple environments (Xiaohongshu is highly sensitive to new accounts and multi-environment logins and will trip its "too many devices" risk control).
- For platforms with short-lived sessions (Xiaohongshu, for instance), closing the browser drops the login, so keep the browser open while you use it.

4. Domain zones (round one, first batch tested 2026-10-07)

Academic:
  Direct: arxiv (search/detail), OpenAlex, PubMed, Wanfang, Baidu Scholar
  Access required: CNKI; **you yourself must hold CNKI access** (campus / institutional / personal account);
      rule: **search, read and download single articles only; bulk is strictly forbidden** (CNKI is the best-known enforcement hotspot for bulk downloads);
      implemented through the cnki skill family (with your own CNKI access); the published package offers usage notes but carries no account and bypasses no permission
  Fixable: Semantic Scholar (anonymous rate limiting returns 429, and a free key opens it); apply for the free key at semanticscholar.org/product/api, then `export SEMANTIC_SCHOLAR_API_KEY=...`; **dblp (the official API is blocked by the Anubis anti-bot shield, so this pack's in-house `dblp find/author/venue/paper`, browser build, slips past the shield automatically)**
  Proxy required inside China: Google Scholar
Engineering:
  Direct: Stack Overflow, MDN, Hacker News, dev.to, GitHub Trending
Culture:
  Direct: Douban (hot lists for books, film and music)
  Proxy required inside China: Wikipedia
Frontier:
  Direct: OpenReview (AI papers and reviews)
  Proxy required inside China: Hugging Face
Consumer:
  Direct: SMZDM (deal search), Eastmoney (hot stock list)

Second batch (2026-10-07):
  Direct: Juejin (hot list), Hupu (hot posts), Nowcoder (interview write-ups), IMDb, OEIS (sequences), NVD (vulnerability database), RFC (protocol docs), weather (wttr), JD.com (product detail / price), Apple Podcasts (search / episode list)
  Login required: Taobao, Maimai, linux.do

(Cleanup log: things that cannot be done and are not essential were deleted outright. DuckDuckGo/Brave (blocked), BBC/Reuters (blocked), Xiaoyuzhou (needs a token, and transcription is already covered by another route), V2EX (not reachable on this network), Suno, 1point3acres, Docker Hub, dictionaries (upstream failing), the Internet Archive, Product Hunt. No more "pending" placeholders.)

Site-selection red lines (set 2026-10-07):
  1. Political, religious or illicit sites: never included (not routed, not listed, not promoted)
  2. Official or public-institution platforms (government affairs, railways, schools, hospitals and the like): excluded by default
  3. Services handling real-name or sensitive data (orders, housing-fund, banking): forbidden
  4. Content, entertainment or tool sites: this pack's domain, welcome

Design stance: this pack defaults to "direct connection inside China first"; sites that need a proxy are labelled honestly and are not recommended by default.

5. Follow-up test, 2026-10-10 (music-reference search in practice)

- Web read: Baidu Baike works (note: for a missing entry it returns the home-page template without an error, and the body is mixed with navigation noise); a Sogou redirect link for WeChat Official Accounts works (web read reads it directly).
- Wikipedia is unreachable on this network (a proxy is needed, consistent with the record above; do not retry the Chinese Wikipedia and burn budget).

(End)
