# MCP access for AI-first clients

Caishi is not limited to the command line. The standalone package [`caishi-mcp`](./caishi-mcp/) is a **self-contained MCP server**: the protocol layer (initialize / tools/list / tools/call / JSON-RPC framing) is implemented in the package itself, with no MCP SDK dependency; the browser engine is the official opencli engine (`@jackwener/opencli`, installed automatically with the package). It plugs into any MCP-capable AI client: Claude Code, Claude Desktop, Codex, Cursor, OpenCode, DeepSeek Harness (dsh), Pi and more.

In one sentence: the AI calls a tool over MCP; the tool drives your already-signed-in browser session through the opencli engine, and one tool call pulls the content back.

Chinese version: [MCP.md](./MCP.md)（中文版）

## Install (one command)

```bash
npm install -g caishi-mcp
```

The engine comes with it. Wire the server into your MCP client (for Claude Code, one line: `claude mcp add caishi -- npx caishi-mcp`). Per-client configuration and per-site arguments are in [caishi-mcp/README.md](./caishi-mcp/README.md).

The command-line main route (the `opencli` platform commands) is untouched; MCP is an added channel, not a migration.

## What you can use today

The four site commands are four tools, called directly, each written after real verification, with other platforms ported as needed:

| Tool | What it returns |
|------|------|
| `bilibili/video` | Bilibili video: title, uploader, duration, views/likes/coins/favorites, publish date, description |
| `douyin/detail` | One Douyin post: caption, author, four engagement counts, publish time, music, watermark-free play URL, image set |
| `xiaohongshu/note` | Xiaohongshu note: title, author, body, likes/collects/comments, tags |
| `web/read` | Any page's main text (as plain text): static pages, knowledge bases and JS-rendered pages work; a site that needs login must be signed in once; PDF direct links do not work |

## Usage example

In an AI with MCP wired up, just say:

> Read this article [link] and give me the key points

> What is this Bilibili video about [link]

## Limits (honest)

- **Dependency**: the browser engine is the official opencli engine (a third-party open-source piece). Caishi's **main route remains the opencli command line**; MCP is an added channel, not a migration, so an upstream change leaves the main route untouched.
- **Philosophy unchanged**: read-only, no bulk, through your own signed-in browser session (the same as the command-line version).
- **Login state**: for sites that require it, sign in once in that same browser (valid long-term).
- **No coverage promise**: web pages differ wildly, and cases that cannot be read are real (PDFs, strong anti-scraping, login walls). The tool reports the error honestly rather than forcing a guess.

## License

Caishi's adapters and protocol layer are original to this project (code MIT, same repository); the browser engine is the official opencli package, used under its terms.
