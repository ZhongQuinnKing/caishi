# MCP access for AI-first clients

Caishi is not limited to the command line. Through [opencli-mcp](https://github.com/jackwener/opencli-mcp) (by opencli's own author, Apache-2.0), the same browser bridge plugs into any MCP-capable AI client: Claude Code, Claude Desktop, Codex, Cursor, OpenCode, DeepSeek Harness (dsh), Pi and more.

In one sentence: opencli-mcp lets an AI drive your already-signed-in Chrome over MCP; Caishi's adapters attach as site adapters, so a single tool call pulls the content back.

Chinese version: [MCP.md](./MCP.md)（中文版）

## Install (two pieces)

1. opencli-mcp (which bundles a Chrome extension):

   ```bash
   npm install -g opencli-mcp
   opencli-mcp setup        # connects to Chrome, then tick your MCP client when prompted
   ```

   The extension can also come from the Chrome Web Store; where the network is awkward, download the zip from its GitHub Releases and load it manually.

2. Caishi's adapters:

   ```bash
   bash install.sh          # installs mcp-adapters/ into ~/.opencli-mcp/adapters/
   ```

   Enable sites as needed on first use: tell the AI "sites.enable web" (the same for Bilibili / Douyin / Xiaohongshu, swapping in the site name).

An easier route: just `npm install -g caishi-mcp`. The standalone package carries its own four-site adapters and launcher, so there are no files to move by hand (see [caishi-mcp/README.md](./caishi-mcp/README.md)).

## What you can use today

The MCP surface is a single tool, `site_run`; the four site commands go through it, each written after real verification, with other platforms ported as needed:

| Site command | What it returns |
|------|------|
| `bilibili` / `video` | Bilibili video: title, uploader, duration, views/likes/coins/favorites, publish date, description |
| `douyin` / `detail` | One Douyin post: caption, author, four engagement counts, publish time, music, watermark-free play URL, image set |
| `xiaohongshu` / `note` | Xiaohongshu note: title, author, body, likes/collects/comments, tags |
| `web` / `read` | Any page's main text (as plain text): static pages, knowledge bases and JS-rendered pages work; a site that needs login must be signed in once; PDF direct links do not work |

The four sites come in the standalone package [`caishi-mcp`](./caishi-mcp/), one command away: `npm install -g caishi-mcp`. Per-site arguments, returned fields and install details are in [caishi-mcp/README.md](./caishi-mcp/README.md).

## Usage example

In an AI with MCP wired up, just say:

> Read this article [link] and give me the key points

> What is this Bilibili video about [link]

## Limits (honest)

- **Dependency**: the MCP route depends on opencli-mcp (a third-party open-source piece). Caishi's **main route remains the opencli command line**; MCP is an added channel, not a migration, so an upstream change leaves the main route untouched.
- **Philosophy unchanged**: read-only, no bulk, through your own signed-in browser session (the same as the command-line version).
- **Login state**: for sites that require it, sign in once in that same browser (valid long-term).
- **No coverage promise**: web pages differ wildly, and cases that cannot be read are real (PDFs, strong anti-scraping, login walls). The tool reports the error honestly rather than forcing a guess.

## License

Caishi's adapters are original to this project (code MIT, same repository); opencli-mcp is Apache-2.0 and used under its terms.
