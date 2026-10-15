# 采诗 · caishi-mcp —— Glama 收录用 Dockerfile（stdio MCP 服务器）
# 健康检查口径：镜像起得来、能应答 initialize 与 tools/list（stdio 行式 JSON-RPC）。
# 实测：本机 node 进程级探针 initialize 与 tools/list 均通（浏览器桥为调用时惰性连接，
# 启动与内省不依赖 Chrome）。构建上下文＝本目录（caishi-mcp/）。
FROM node:22-slim
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY bin/ bin/
COPY mcp-adapters/ mcp-adapters/
COPY server.json ./
COPY LICENSE ./
CMD ["node", "bin/launch.mjs"]
